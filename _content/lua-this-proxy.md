# Lua 的 `this` 代理（LuaProxy）

<!-- source: psych/script/LuaProxy.hx -->
<!-- source: psych/script/FunkinLua.hx -->

## `this` 是什么

每个 Lua 脚本在创建时都会拿到一个全局 `this`：

```haxe
// FunkinLua 构造函数（source/psych/script/FunkinLua.hx:220）
setProxy('this', getScriptState());
```

`getScriptState()` 返回的是：

| 场景 | `this` 指向 |
| --- | --- |
| 歌曲内运行的脚本 | `PlayState.instance` |
| 由 `LuaSState` 启动的菜单脚本 | 当前菜单状态（`FunkinLua.currentMenuState`，回退到 `menuOwner` / `FlxG.state`） |

这是 Psych 0.7 遗留下来的 `this`，Parker Engine 把它从「属性快照」改成了**实时代理**。

## 为什么要用代理

引擎把 Haxe 值交给 Lua 走的是 `llua.Convert.toLua()`。它的行为是「把实例的字段转成一张一次性的表」，而且**只递归一层**——表里再遇到对象字段就变成 `nil`。所以老实现里：

```lua
-- 旧行为（现在是错的写法带来的观感）
this.camGame:flash(0xffffffff, 1)   -- camGame 是 nil，直接报错
```

`LuaProxy` 换了个思路：表里**只放一个数字 id**（字段名 `__pklua_ref`），真正的读写都通过元表回到 Haxe 侧的活对象上。于是

```lua
this.camGame:flash(0xffffffff, 1)        -- 真的闪白 camGame
this.camGame.zoom = 1.2                  -- 真的改了相机缩放
this.boyfriend:playAnim('idle')          -- 真的播放 BF 的 idle
this.boyfriend.animation.curAnim.name    -- 真的读得到当前动画名
local hp = this.health                   -- 读任意 PlayState 字段
```

都能落到真正的引擎对象上。

> 注意 `this.boyfriend:playAnim('idle')` 用的是 `Character.playAnim(anim, forced, reverse, startFrame)`，而不是 `spr.animation.play`——所以角色偏移、sing 时长等逻辑都会正常生效。

## 语法限制：`this:camGame:flash(...)` 是语法错误

**这是 Lua / Luau 语言本身的限制，引擎无法兼容。**

`a:b(...)` 这种冒号语法**必须是方法调用**，`a` 只能是「对象」，`b` 只能是方法名。而下面这种写法：

```lua
this:camGame:flash(0xffffffff, 1)   -- ✗ 解析错误（parse error）
```

在解析阶段就会被拒绝：解析器读到 `this:camGame` 后会期待一个函数调用，紧接着又出现 `:flash(...)`，语法不通。这和 `this` 是不是代理表无关——换成任何普通表也一样报错。

正确写法只有两种：

```lua
this.camGame:flash(0xffffffff, 1)   -- ✓ 点号取字段，冒号调方法
this.camGame.flash(this.camGame, 0xffffffff, 1)  -- ✓ 等价显式写法（一般不需要）
```

## 代理的读写规则

- **读字段**：`__index` → `LuaProxy.luaIndex()` → `Reflect.getProperty()`。
  - `nil` / 数字 / 字符串 / 布尔 → 原样返回值。
  - 函数 → 交回一个**闭包**，调用时走 `__pklua_invoke()`。
  - 其他对象 / 数组 / Map / Class → 再包一层代理表。
  - 读失败（Haxe 抛异常）会在屏幕上红字报告 `LuaProxy: could not read "xxx" ...`，然后把 `nil` 返回给脚本。
- **写字段**：`__newindex` → `LuaProxy.luaSetProp()`。
  - Map 走 `set()`，数组按数字下标赋值（`t[1]` 对应 Haxe 的 `[0]`，越界会 `push`）。
  - 其他对象走 `Reflect.setProperty()`。
  - **引擎对象上没有这个字段时写操作返回 `false`，于是 Lua 侧的 `__newindex` 会 `rawset` 把它留在代理表里**。好处是脚本自己的记账字段（`spr.myFlag = true`）不会报错；代价是**拼错字段名也不会报错**，值只是留在 Lua 那张表里，永远到不了引擎。写失败被刻意静默（源码注释：「this is not a failure worth a screen full of red text on every `spr.customFlag = true`」）。
- **调用方法**：`obj.method(args)` 与 `obj:method(args)` **都可用**。Haxe 的成员函数（`HX_DEFINE_DYNAMIC_FUNC*`）本身已经绑定了对象，所以引擎侧不传 `this`；Lua 侧的闭包还会检测「第一个参数是不是指向同一个 id 的代理表」，是就先丢掉——这就是冒号写法能工作的原因。
- **`Class:new(...)` / `Class.new(...)`**：如果代理指向的是一个**类**（不是实例），读 `new` 会得到一个构造用的函数，调用它会 `Type.createInstance()` 并返回新实例的代理。读类上的其他字段时，引擎**只查静态字段**（`Type.getClassFields()`），因为 hxcpp 下随意读类字段会白白 new 一个实例出来。
- **数组**：只有 `index > 0` 才会被当作数组下标（`t[1]` → Haxe `arr[0]`）；`#t`（`__len`）只对数组有意义，其他对象返回 `0`；`tostring(t)`（`__tostring`）返回 `Std.string(实际值)`。
- **同一个 Haxe 对象总是同一张代理表**：`refIds` 按对象身份缓存，`__pklua_wrapped` 又用弱表缓存，所以同一个 Lua 状态里 `this.boyfriend == this.boyfriend` 为真。**但 `this.boyfriend` 和其它来源的同一个对象不保证相等**（不同脚本的 Lua 状态、或另一条注入路径），比较对象请比较名字/标签而不是表本身。
- **代理可以作为参数传回引擎**：`LuaProxy.unwrap()` 会把带 `__pklua_ref` 的表还原成真正的 Haxe 对象（数组会逐项还原）。所以 `setProperty('x.y', this.boyfriend)` 这类写法是可行的。

## 生命周期与范围

- **只有 `this` 是代理。** 引擎里 `FunkinLua.set()` 绑定的其它全局（`curStep`、`curBeat`、`bpm`、`score`、`health`、`defaultPlayerStrumX0` 等等）都是**基本类型快照**，不是代理。更重要的是：在本分支里 `camGame` / `camHUD` / `boyfriend` / `dad` / `gf` / `notes` / `strums` 这些对象**只通过 `setOnHScripts()`（HScript）和 `setOnScripts()`（LScript + Python）注入**（`PlayState.setOnScripts()` 的实现里只列了这两个），**Lua 脚本并没有这些全局名**。所以在 Lua 里：

  ```lua
  camGame.zoom = 1.2        -- ✗ camGame 是 nil
  this.camGame.zoom = 1.2   -- ✓ 走代理
  setProperty('camGame.zoom', 1.2)  -- ✓ 走名字查找
  ```

  也就是说，Lua 侧访问活对象有两条路：**`this.<字段>` 代理**，或者**名字查找**——`getProperty` / `setProperty` / `playAnim` / `getObjectOrder` / `screenCenter` 这类函数接受的对象路径，最终都会回落到 `Reflect.getProperty(PlayState.instance, 名字)`，所以直接传 `'camGame'`、`'boyfriend'`、`'dad'`、`'gf'` 是有效的。
- **id 只在脚本存活期间有意义**：`FunkinLua.stop()`（脚本被停止、场景销毁、或 `close()` 后回调返回）会调用 `proxy.dispose()`，清空 `refs` / `refIds`。此后再用一张留着没放的代理表，读会得到 `nil`、写只会 `rawset` 到那张表上。
- **桥装不上时不会让脚本崩**：`install()` 里解析或执行 Lua 预置代码失败时，会在屏幕上红字报 `LuaProxy: could not ...`，代理表保持惰性（读写都失败），脚本其余功能照常。
- **占用了一批全局名**：桥会向脚本的全局表写入 `__pklua_proxy`、`__pklua_wrap`、`__pklua_decode`、`__pklua_wrapped`、`__pklua_index`、`__pklua_invoke`、`__pklua_setprop`、`__pklua_len`、`__pklua_tostring`。**自己的脚本不要用这些名字**，否则桥会被破坏。
- **同样的机制也用在 `.lscript`**：`script/FunkinLScript.hx` 用它推送值，所以 `.lscript` 的 `this` 本来就是「真状态」。这次改动只是让 `.lua` 和 `.lscript` 行为一致。

## 常见写法对照

| 目的 | 写法 |
| --- | --- |
| 闪白主相机 | `this.camGame:flash(0xffffffff, 1)` |
| 改相机缩放 | `this.camGame.zoom = 1.2` |
| 让 BF 播放 idle | `this.boyfriend:playAnim('idle')` |
| 读当前动画名 | `debugPrint(tostring(this.boyfriend.animation.curAnim.name))` |
| 读血量 | `local hp = this.health` |
| 改血量 | `this.health = 1.5` |
| 让对手跳舞 | `this.dad:dance()` |
| 读第 3 个 strum 的 x | `local x = this.strumLineNotes.members[3].x` |
| 调 PlayState 的方法 | `this:startCountdown()` 或 `this.startCountdown(this)` |
| 访问菜单态的成员 | `this.members`（菜单脚本里 `this` 是那个状态本身） |

**反例（不要写）**：

```lua
this:camGame:flash(0xffffffff, 1)   -- ✗ 语法错误
boyfriend:playAnim('idle')          -- ✗ Lua 里没有 boyfriend 这个全局
camGame.zoom = 1.2                  -- ✗ Lua 里没有 camGame 这个全局
this.boyfreind.x = 0                -- ✗ 拼错字段名不会报错，值只会留在 Lua 表里
```
