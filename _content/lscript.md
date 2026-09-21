<!-- source: script/FunkinLScript.hx -->
<!-- source: script/LScriptSState.hx -->
<!-- source: script/GlobalScript.hx -->
<!-- source: script/ScriptDebugOverlay.hx -->
<!-- source: FNFGame.hx -->
<!-- source: states/game/PlayState.hx -->
<!-- source: backend/Paths.hx -->

# LScript（`.lscript`）

> **适用版本：Parker Engine 0.2.8**（`Project.xml` 的 `<app version>`）。参考工具链：Haxe 4.3.7 + HaxeFlixel。
>
> **本文以源码为准。** 每条 API、回调、路径都是从引擎源码里读出来的；白名单里「有名字、但当前派发点用的是 `callOnLuas()` 所以到不了 LScript」的回调，都在 §3.1 表里明确标注为**不会到达 LScript**。

`.lscript` 是 Parker Engine 自带的 **Luau 运行时**，由 `source/script/FunkinLScript.hx` 全权实现，底层直接使用 `llua` 的 `Lua` / `LuaL` / `Convert`（和 `psych/script/FunkinLua.hx` 驱动 `.lua` 用的是同一套 plumbing）。

它 **不是 haxelib**：仓库里没有 `lscript` 依赖，`Project.xml` / `hmm.json` 里也找不到它，任何地方都不要 `import lscript.*`。整个类体包在 `#if LUA_ALLOWED` 内；未开启时 `FunkinLScript` 退化成空壳，只在屏幕上打印一句 `LUA support is disabled. Script functionality is limited.`。

脚本源码通过 `LuaL.luau_loadsource(lua, chunkName, code)` 加载，chunk 名就是文件路径（Luau 的报错会指到具体文件）。`.lua` 脚本走的也是同一个 `luau_loadsource`，因此两者跑在同一个 VM 上——区别不在语言，而在 API 面、回调白名单和 parent 模型（见 §7）。

---

## 1. 文件放在哪 / 自动发现

`.lscript` 的自动发现路径和 `.lua` 一致（都是按「当前 mod → 全局 mod → `mods/` 根 → `assets/`」查找），因此换扩展名即可迁移：

| 位置 | 加载者 | 时机 | 说明 |
|---|---|---|---|
| `scripts/<name>.lscript` | `PlayState.loadGlobalScripts()` | 歌曲 `create()` 早期 | 只扫目录一层，**不递归**；重名文件按 mod 优先级只加载一次 |
| `data/<formatted-song>/<name>.lscript` | `PlayState.loadSongScripts()` | `initScripts()` | 歌曲专属脚本，`<formatted-song>` 走 `Paths.formatToSongPath()`（小写、空格转 `-`） |
| `stages/<stage>.lscript` | `PlayState.startLuahxOnFolder()` | 建台阶段 | 舞台脚本 |
| `custom_notetypes/<type>.lscript` | `startLuahxOnFolder()` | 遇到该 note type 时 | 自定义 note 类型脚本 |
| `custom_events/<event>.lscript` | `startLuahxOnFolder()` | 遇到该事件时 | 自定义事件脚本 |
| `states/<StateName>.lscript` | `FNFGame.switchState()` → `LScriptSState` | 状态切换时 | 替换内置状态，见 §8 |
| `modifiers/<name>.hscript` | `HScriptModifier.fromName()` | 未启用 | 那是 HScript 修饰器，不是 LScript，见 modchart 文档 |

查找顺序（mod 优先）：`Paths.modFolders(file)` 命中就用 mod 里的，否则用 `Paths.getPreloadPath(file)`（即 `assets/`）。

**注意：`characters/<name>.lscript` 不会被加载。** `PlayState.initCharScript()` 只用 `HScriptUtil.extns`（`.hx` / `.hscript` / `.hsc` / `.hxs`）查找角色脚本，没有 `.lscript` 分支。角色逻辑请写 HScript。

---

## 2. 生命周期与加载顺序

`FunkinLScript` 的构造分三步：

1. `createState()` —— `LuaL.newstate()` + `LuaL.openlibs()`，失败只报错不抛异常；
2. `installBridge()` —— 先跑 Lua 侧的桥（`PRELUDE`），再把 `__lscript_index` / `__lscript_invoke` / `__lscript_setprop` / `__lscript_len` / `__lscript_tostring` / `__lscript_call` 六个 Haxe 函数绑成全局；
3. `setupEnvironment()` —— 把类、工具函数、`this`、`add`/`remove`/`insert`/`members`、`foreground` 等全部绑定，然后写入 `defaultVars` 里的公共变量。

脚本主体 **不** 在构造里执行。真正的顺序（歌曲内由 `PlayState.initLScript()` 驱动）是：

```
new FunkinLScript(filePath)      -- 建 VM、绑环境，不跑脚本
  → lscriptArray.push(script)
  → onAddSScript()               -- 向所有 lscript 推 curStep/curBeat/bpm/camGame/角色/notes…（见 §5）
  → script.execute()             -- 读文件 → runChunk() → call('onCreate')
  → script.setParent(this)       -- this / game / add / remove / insert / members 指向 PlayState
```

`execute()` 只会跑一次（`executed` 标志），第二次调用是 no-op。`runChunk()` 用 `Lua.pcall` 保护，解析错误 / 运行期错误 / 从绑定函数里逃出来的 Haxe 异常都会被 `scriptMessage()` 报出来，**不会** 直接结束进程；chunk 失败时该脚本的 VM 会被 `closeState()` 关掉（`lua = null`），之后所有 `call()` 直接返回 `Function_Continue`。

`stop()` 会置 `closed = true`；如果此刻脚本代码正在栈上运行（`running == true`，即从回调内部自杀），则只做标记，由正在执行它的那一层（`call()` / `runChunk()`）在返回后关闭 VM。

---

## 3. CALLBACKS 白名单（共 47 条）

`FunkinLScript.CALLBACKS` 是 **回调白名单**：`call(method, args)` 先查 `CALLBACKS.contains(method)`，不在名单里的名字会被拒绝，并在屏幕上打一条红字：

```
FunkinLScript<path>: "<name>" is not a dispatchable callback, skipping it
```

同时返回 `Function_Continue`。引擎新增回调时必须往这个数组里补名字，否则分发不进去。

### 3.1 全表

「参数」列是该回调在 `callOnScripts(event, args)` 里实际传给 LScript 的实参；「派发点」只列 `states/game/PlayState.hx` 的行号（`LScriptSState` 自己派发的单独标注）。

| 回调名 | 触发时机 / 派发点 | 参数 |
|---|---|---|
| `onCreate` | 脚本主体执行完之后立刻（`FunkinLScript.execute()` 内部，PlayState:6159 `initLScript`） | 无 |
| `onCreatePost` | PlayState `create()` 尾部（:1310）；LScriptSState 在 `super.create()` 之后 | 无 |
| `onLoad` | 紧接 `onCreatePost`（:1311）；LScriptSState 构造里、脚本主体之后 | 无 |
| `onStartCountdown` | 倒计时开始（:1850） | 无 |
| `onCountdownTick` | 倒计时每个 tick（:2052），共 5 次（swagCounter 0→4） | `swagCounter:Int` |
| `onSongStart` | 歌曲正式开始（:2243） | 无 |
| `onStepHit` | 每一步（:5228）；LScriptSState `stepHit()` | `curStep:Int` |
| `onBeatHit` | 每一拍（:5337）；LScriptSState `beatHit()` | `curBeat:Int` |
| `onSectionHit` | 每一段（:5372） | `curSection:Int` |
| `onUpdate` | 每帧（:2798）；LScriptSState `update()` 最先 | `elapsed:Float` |
| `onUpdatePost` | 每帧、`super.update()` 之后（:3293）；LScriptSState 同位置 | `elapsed:Float` |
| `onSpawnNote` | note 生成进 `notes` 组时（:3052） | `note:Note` |
| `onMoveCamera` | 镜头要跟随某个角色时（:3905 / :3914 / :3920） | `gf` / `dad` / `boyfriend`（角色对象，不是字符串） |
| `goodNoteHit` | 玩家命中（:4970） | `note:Note` |
| `opponentNoteHit` | 对手命中（:4850） | `note:Note` |
| `noteMiss` | 玩家漏接（:4739） | `daNote:Note` |
| `noteMissPress` | 空按（没有对应 note，:4790） | `direction:Int` |
| `popUpScore` | 每次弹出评分/连击提示（:4426） | `rating:String`, `comboSpr:FlxSprite`, `numScore:FlxSprite` |
| `onUpdateScore` | `updateScore(miss)` 尾部（:2141） | `miss:Bool` |
| `onRecalculateRating` | 重算评级（:5989） | 无 |
| `SkinNoteSplash` | `spawnNoteSplash()` 里（:5005），此时 `skin` 还是默认值 `'noteSplashes'`，且返回值被忽略——纯通知 | `skin:String` |
| `onEvent` | 每个事件触发（:3890） | `eventName:String`, `value1:String`, `value2:String` |
| `eventEarlyTrigger` | 每帧检查待触发事件时（:2535） | `event:String`, `value1:String`, `value2:String`, `strumTime:Float` |
| `onPause` | 暂停（`callOnScriptAll('onPause')`，:3298）；返回 `Function_Stop` 可阻止暂停 | 无 |
| `onResume` | 恢复（:2683） | 无 |
| `onGameOver` | 死亡判定通过、进 GameOver 之前（:3364） | 无 |
| `onEndSong` | 歌曲正常结束（:4076） | 无 |
| `onDestroy` | `PlayState.destroy()` 里逐脚本调用（:5164）；LScriptSState `destroy()` | 无 |
| `onDestroyPost` | **只有** `LScriptSState.destroy()` 会派发（:126）；歌曲内不会被调用 | 无 |
| `preModifierRegister` | 建好 strums 之后、注册内置修饰器之前（:1881） | 无 |
| `postModifierRegister` | 注册内置修饰器之后（:1884） | 无 |
| `generateModchart` | 倒计时每个 tick，与 `onCountdownTick` 同处（:2055），共 5 次 | 无 |
| `onCountdownStarted` | 只经 `callOnLuas` 派发（:1903）——**当前不会到达 LScript** | 无 |
| `onEventSet` | 只经 `callOnLuas` 派发（:5225）——**不会到达 LScript** | `curStep` |
| `onGhostTap` | 只经 `callOnLuas`（:4527）——**不会到达 LScript** | `key` |
| `onKeyPress` | 只经 `callOnLuas`（:4551）——**不会到达 LScript** | `key` |
| `onKeyRelease` | 只经 `callOnLuas`（:4578）——**不会到达 LScript** | `key` |
| `onNextDialogue` | 只经 `callOnLuas`（:2180）——**不会到达 LScript** | `dialogueCount` |
| `onSkipDialogue` | 只经 `callOnLuas`（:2185）——**不会到达 LScript** | `dialogueCount` |
| `onUpdateOptions` | 只经 `callOnLuas`（`FunkinLua:5296`）——**不会到达 LScript** | `elapsed` |
| `onGameOverStart` | 只经 `callOnLuas`（`GameOverSubstate:47`）——**不会到达 LScript** | 无 |
| `onGameOverConfirm` | 只经 `callOnLuas`（`GameOverSubstate:125/199`）——**不会到达 LScript** | `?restart:Bool` |
| `onCustomSubstateCreate` | 只经 `callOnLuas`（`FunkinLua:5395`）——**不会到达 LScript** | `name` |
| `onCustomSubstateCreatePost` | 只经 `callOnLuas`（`FunkinLua:5397`）——**不会到达 LScript** | `name` |
| `onCustomSubstateUpdate` | 只经 `callOnLuas`（`FunkinLua:5409`）——**不会到达 LScript** | `name`, `elapsed` |
| `onCustomSubstateUpdatePost` | 只经 `callOnLuas`（`FunkinLua:5411`）——**不会到达 LScript** | `name`, `elapsed` |
| `onCustomSubstateDestroy` | 只经 `callOnLuas`（`FunkinLua:5416`）——**不会到达 LScript** | `name` |

统计：47 条在名单内；其中 **32 条**在当前源码里真的会被分发给 LScript，另外 **15 条**（`onCountdownStarted`、`onEventSet`、`onGhostTap`、`onKeyPress`、`onKeyRelease`、`onNextDialogue`、`onSkipDialogue`、`onUpdateOptions`、`onGameOverStart`、`onGameOverConfirm`、`onCustomSubstate*` 五条）只被 `callOnLuas()` 派发，也就是「只有 `.lua` 收得到」。它们留在白名单里是为了让脚本写了也不报错。

### 3.2 分发语义

* **未定义的回调被跳过**：`call()` 直接 `Lua.getglobal(method)`，取到的不是 function 就 `pop` 掉、静默返回 `Function_Continue`。不再有旧 `lscript` 那个把未定义全局转发到 `script.parent` 的 `_G` 元表，所以「回调没写」永远不会崩进程。
* **回调内报错**：`Lua.pcall` 捕获后 `scriptMessage()` 上屏，返回 `Function_Continue`。
* **返回值**：回调返回 `nil` / 什么都不返回 → 引擎链保持 `Function_Continue`。返回 `Function_Stop` / `Function_Continue` / `Function_Halt`（这三个全局是字符串 `'FUNC_STOP'` / `'FUNC_CONT'` / `'FUNC_HALT'`）时按同名字符串比较，语义与其他脚本一致：`Function_Stop` 在 `ignoreStops = false` 的调用点会中断后续脚本。
* **暂停的脚本永远不会被分发**：`call()` 开头 `if (paused) return Function_Continue;`。

类型判断不走 `Lua.LUA_TFUNCTION`（预编译 Luau 库与 vendored `lua.h` 的枚举不一定一致），而是 `Lua.typename(lua, Lua.type(lua, i))` 字符串比较。

---

## 4. 引擎注入的全局 API

`setupEnvironment()` 绑定的全部名字（`set()` 对函数走 `bind()`，其余走 `pushValue()`）：

**核心类 / 工具**

`FlxG`、`FlxSprite`、`FlxGraphic`、`FlxBasic`、`FlxObject`、`FlxCamera`、`FlxSpriteGroup`、`FlxTypedGroup`、`FlxVideo`、`FlxVideoSprite`、`PsychVideoSprite`、`ParkerVideoSprite`（= `PsychVideoSprite`）、`Handle`、`FlxTween`、`FlxEase`、`FlxTimer`、`FlxText`、`FlxTextFormat`、`FlxShader`、`FlxRuntimeShader`、`ShaderFilter`、`FlxSound`、`FlxAxes`（表 `{X, Y, XY}`）、`Lib`、`Capabilities`、`BlendMode`（表，12 个模式）、`Std`、`Type`、`Reflect`、`Math`、`StringTools`、`Json`（表 `{parse, stringify}`）

**引擎类**

`PlayState`、`game`（= `PlayState.instance`，非歌曲状态里是 nil，`LScriptSState` 会覆盖成自己）、`Paths`、`ClientPrefs`、`Note`、`StrumNote`、`NoteSplash`、`Character`、`Boyfriend`、`Section`、`Conductor`、`WeekData`、`Highscore`、`StageData`、`Song`

**常量与函数**

| 名字 | 说明 |
|---|---|
| `Function_Stop` / `Function_Continue` / `Function_Halt` | 回调返回策略，值为字符串 `'FUNC_STOP'` / `'FUNC_CONT'` / `'FUNC_HALT'` |
| `print(...)` | 任意参数，拼成一行送 `scriptMessage()`（白字） |
| `import(className, ?varName)` | 见下方说明 |
| `add(obj, ?front)` / `remove(obj)` / `insert(pos, obj)` / `members` | 先绑到 `FlxG.state`，`setParent()` 之后再指向真正的 state |
| `foreground` | 见 §9 的限制 |
| `this` | 脚本运行的状态（`setParent()` 之前是 `PlayState.instance`，否则 `FlxG.state`） |
| `pauseScript()` / `resumeScript()` | 暂停/恢复自己 |
| `setScriptPaused(tag, paused)` | 按 tag 暂停/恢复任意脚本（`PlayState.setScriptPaused`） |
| `addTouchPad(DPad, Action)` / `removeTouchPad()` | 仅 `#if android` |
| `FileSystem` / `File` / `Sys` | 仅 `#if sys` |

**只有正在玩歌时才注入**（`FlxG.state is PlayState && PlayState.instance != null`）：

| 名字 | 说明 |
|---|---|
| `modManager` | `PlayState.modManager`，Modchart 修饰器管理器（也是个代理表） |
| `global` | 当前 state 的 `variables:Map<String, Dynamic>`（`MusicBeatState` 字段），可读写 |
| `setGlobalFunc(name, func)` | 往 `variables` 里塞函数 |
| `callGlobalFunc(name, args)` | 调用它 |
| `createGlobalCallback(name, func)` | 同时塞给**所有** `.lua` 脚本（并写进 `FunkinLua.customFunctions`），用于跨脚本回调 |

另外 `PlayState.onAddSScript()` 在每个 LScript 创建后（`execute()` 之前）通过 `setOnScripts()` 推一批变量：`curStep`、`curSection`、`curBeat`、`bpm`、`camGame`、`camHUD`、`camOther`、`camFollow`、`camFollowPos`、`boyfriend`、`dad`、`gf`、`boyfriendGroup`、`dadGroup`、`gfGroup`、`notes`、`strumLineNotes`、`playerStrums`、`opponentStrums`、`unspawnNotes`。对象以代理表形式给出（活的），**数字是值拷贝**（死的）——见 §9。

`import()` 的三种用法（`importClass()`）：

```lua
import('flixel.FlxSprite')                 -- 按类名末段绑定：全局 FlxSprite
import('flixel.FlxSprite', 'Spr')          -- 绑定为指定名字
import('flixel.*')                          -- 取最长可解析前缀的类，把它的静态字段逐个绑成全局
```

---

## 5. 代理表机制

脚本看到的「引擎对象」不是快照，而是代理表（proxy table），所有读写/调用都回到 Haxe：

* `pushValue(value)` 分流：`null` → `nil`，`Bool` / `Int` / `Float` / `String` → 原生值，`Function` → 可调用闭包（也走 `bind()`），**其他一切（包括 Class）** → `pushProxy()`。
* 代理表只有一个字段 `__lscript_ref`，里面是 Haxe 值的 id；metatable 是 `PRELUDE` 里的 `__lscript_proxy`：

| 元方法 | 回调 Haxe | 行为 |
|---|---|---|
| `__index(t, key)` | `luaIndex(ref, key)` | 读字段 |
| `__newindex(t, key, value)` | `luaSetProp(ref, key, value)` | 写字段 |
| `__len(t)` | `luaLen(ref)` | `#t`，只对数组返回长度，其他一律 0 |
| `__tostring(t)` | `luaToString(ref)` | `tostring(t)` |

* **同一个 Haxe 值永远给同一张表**：`__lscript_wrapped` 是 weak-value 缓存，`registerRef()` 也用 `ObjectMap` 去重。`spr == spr` 成立。
* **桥的返回值协议**：Haxe 端返回 `[kind, value]` 描述符——`[0]` = 无（Lua 侧得到 `nil`，用 `KIND_NONE` 而不是裸 `nil`，避免和数字 0 混淆）、`[1]` = 值、`[2]` = 函数、`[3]` = 另一个代理的 ref。Lua 侧的 `__lscript_decode()` 负责还原。

各方法的细节（都带 try/catch，出错只 `reportFailure()` 上屏，不抛进 VM）：

| 调用 | 支持的目标 |
|---|---|
| `luaIndex` | `IMap` → `map.get(key)`；类 → 只查 `Type.getClassFields()` 里的静态字段（`'new'` 单独处理）；数组 → 数字键；其余 → `Reflect.getProperty()` |
| `luaSetProp` | `IMap` → `map.set(key, v)`；数组 → 按下标赋值，越界则 `push`；其余 → `Reflect.setProperty()` |
| `luaInvoke` | 类 + `key == 'new'` → `Type.createInstance()`；`IMap` → 取 map 里的函数；其余 → `Reflect.getProperty()` 再 `Reflect.callMethod(null, fn, args)` |

几点由此推出的语法事实：

* **数组下标是 1-based**：`arrayIndex()` 把 Lua 传来的 `name` 转成 Haxe 下标时是 `index > 0 ? index - 1 : -1`，也就是 `proxy_arr[1]` → Haxe `arr[0]`；而 `proxy_arr[0]` 会当成普通字段名去找，结果是 `nil`。遍历用 `for i = 1, #arr do`。
* **方法两种写法都能用**：`spr:playAnim('idle')` 和 `spr.playAnim('idle')` 都行。`:` 语法会把表自身作为第一个参数传进闭包，Lua 侧检测到它是「同一张代理表」就 `table.remove(args, 1)` 丢掉。成员函数本身已携带对象（`HX_DEFINE_DYNAMIC_FUNC*`），Haxe 侧不用再传 `this`。
* **脚本传给引擎的参数会被还原**：`unwrap()` / `unwrapArgs()` 会把代理表换回真正的 Haxe 值（递归处理数组）。
* **类可以 `new`**：`FlxSprite:new(0, 0)` / `FlxSprite.new(0, 0)` 都能构造（走 `Type.createInstance`）。类只暴露静态成员，防止 hxcpp 为了读一个字段而临时造实例。
* **`bind()` 是引擎函数唯一的入口**：Haxe 函数进 `bindings` 表，Lua 侧拿到 `__lscript_bind(name)` 生成的闭包，调用时经 `__lscript_call` → `luaCall()` → `Reflect.callMethod`。函数抛出的异常在这里被捕获并上屏，返回值也在这条路径上被转换。
* `set(name, value)` 对函数自动转 `bind()`，对普通值 `pushValue()`；`setClass(cls)` 按类名末段绑定；`get(name)` / `hasFunction(name)` 用来探测脚本自己的全局。

---

## 6. 与 `.lua` 的差异

| 项目 | `.lua`（`psych/script/FunkinLua.hx`） | `.lscript`（`script/FunkinLScript.hx`） |
|---|---|---|
| VM / chunk 加载 | `llua` + `LuaL.luau_loadsource` | 相同 |
| 回调白名单 | **没有**。`call()` 直接用名字取全局，任意名字都能试 | **有**。`CALLBACKS` 47 条，名单外会上屏报错并跳过 |
| 未定义 / 非 function 的全局 | 返回 `Function_Continue`；若那个值不是 `nil` 还会 `luaTrace` 一条 `ERROR: attempt to call a <type> value` | 静默跳过，不报错 |
| 脚本可见 API | 数百个 Psych 风格 helper（`getProperty`/`setProperty`/`makeSprite`/`doTween*`/`setObjectOrder`…）外加 `ESCompat` 注册的约 70 个「Engine Custom ES」回调 | 只有类/工具全局 + `this`/`game`/`modManager`/`print`/`import` + 暂停与触摸板 helper |
| parent 模型 | `script.parent` + `LuaProxy`（`this` 走 `setProxy()` 才是活的） | **不存在** parent 反射；`this`/`game` 就是代理表，脚本里给全局赋值只留在脚本内，不会落到 state 上 |
| Modchart API | 额外有一整套 Lua 函数：`setValue` / `setPercent` / `getValue` / `getPercent` / `queueSet` / `queueSetP` / `queueEase` / `queueEaseP` / `addBlankMod` | 没有这些函数，改用 `modManager` 代理：`modManager:setValue(...)`、`modManager:queueEase(...)` |
| 状态覆盖 | `states/<Name>.lua` → `LuaSState`，优先级**高于** LScript | `states/<Name>.lscript` → `LScriptSState`，优先级最低 |
| 错误显示 | `luaTrace()`（菜单模式走 overlay，歌曲内走 `addTextToDebug`） | `scriptMessage()` → 有 `PlayState` 走 `addTextToDebug`，否则 `ScriptDebugOverlay.report()` |
| 开关 | `#if LUA_ALLOWED` | 同一个 `#if LUA_ALLOWED` |

移植提示：`.lua` 里最常见的 `setProperty('camGame.zoom', 1.2)`、`makeSprite(...)`、`doTweenX(...)` 在 `.lscript` 里都要改写成代理写法（`camGame.zoom = 1.2`、自己 `FlxSprite:new()`、`FlxTween.tween(...)`）。

---

## 7. `states/<Name>.lscript` 覆盖内置状态

`FNFGame.switchState()` 在切换任何 `MusicBeatState`（且 `state.canBeScripted == true`，默认就是 true）时依次找：

1. `states/globals/<StateName>.hx|.hscript|.hsc|.hxs` → `OScriptState`（**优先级最高**）
2. `states/<StateName>.lua` → `FunkinLua.LuaSState`（`#if LUA_ALLOWED && MODS_ALLOWED`）
3. `states/<StateName>.lscript` → `LScriptSState`（**优先级最低**）

`<StateName>` 是短类名，例如 `TitleState`、`MainMenuState`、`StoryMenuState`、`PlayState`。查找走 `Paths.modFolders('states/...')`（mod 感知）。

`LScriptSState`（`source/script/LScriptSState.hx`，整体在 `#if LUA_ALLOWED` 内）：

* 构造函数 `super(false)` —— **关掉** `canBeScripted`，避免自己被再次覆盖成递归。
* `loadScript('states/<Name>.lscript')`：mod 优先、否则 preload；找不到就 `trace` + `ScriptDebugOverlay.report()` 红字，返回 false。
* 绑定顺序：`new FunkinLScript(scriptPath)` → `setParent(this)`，并把 `this` / `game` / `add` / `remove` / `insert` / `members` 全部指向这个 state（因为 wrapper 绑定时 `PlayState.instance` 可能是 nil、`FlxG.state` 还是旧 state）→ `lscript.execute()` （脚本主体 + `onCreate`）→ 返回后构造函数再调 `onLoad`。
* 生命周期：`create()` → `ScriptDebugOverlay.attach(this)`（顺便把之前排队的报错刷出来）→ `super.create()` → `onCreatePost`；`update()` → `onUpdate`（返回 `Function_Stop` 直接 return，不调 `super`）→ `super.update()` → `onUpdatePost`；`beatHit()` / `stepHit()` 先派发再 `super`；`destroy()` → `onDestroy`（返回 `Function_Stop` 则跳过 `onDestroyPost`）→ `onDestroyPost` → `lscript.stop()`。
* 脚本就在这个 state 上跑：`this` 是它，`add(sprite)` 也加进它。

---

## 8. 报错显示

`FunkinLScript.scriptMessage(msg, color)`：

```haxe
final playState:PlayState = PlayState.instance;
if (playState != null)
    playState.addTextToDebug(msg, color);   // 歌曲内：左下角 debug 文本
else
    ScriptDebugOverlay.report(msg, color);  // 没在玩歌：共享的屏上 overlay
```

`ScriptDebugOverlay` 是 `LuaSState` / `LScriptSState` / `OScriptState` 共用的屏上报错层，`attach(this)` 由 `LScriptSState.create()` 调用；从构造函数里报的消息会先排队，等 `create()` 时一起刷出。overlay 用独立的 `FlxCamera` 并把自己重新追加到 `FlxG.cameras.list` 末尾，所以始终压在 state 的 sprite 和 substates 之上。

会上屏的内容包括：VM 创建失败、chunk 解析/运行失败、回调内异常、白名单拒绝、`import` 失败、`set()` 失败、桥调用失败（读/写/调字段）。

---

## 9. 已知限制与坑

1. **回调必须在白名单里**（§3）；不在名单里的名字连试都不会试，只有一条红字提示。
2. **未定义的回调被静默跳过**——写错一个字（`onBeatHit` 写成 `onbeathit`）不会报错，只是永远不触发；可以用 `hasFunction('onBeatHit')` 自查。
3. **15 条白名单回调当前只有 `.lua` 收得到**（§3.1 表尾），因为派发点用的是 `callOnLuas()`。写了不会报错，但不会执行。
4. **数字全局是快照，不会随歌曲更新**。`curStep` / `curBeat` / `curSection` / `bpm` 由 `onAddSScript()` 在脚本创建时推一次（`setOnScripts`），歌曲中只有 Lua 会被逐 step 更新（`setOnLuas('curStep', ...)`）。**请一律用回调参数**（`onStepHit(step)`、`onBeatHit(beat)`、`onSectionHit(section)`），不要读全局。
5. **`modManager` 在脚本主体执行时可能还是 nil**。顺序是 `initScripts()`（加载并 execute 脚本）→ `generateSong()` → `new ModManager()` → `setDefaultLScripts("modManager", ...)`。所以脚本顶部别缓存它，在回调里用全局名。
6. **没有 `script.parent`**。脚本里给全局赋值是给自己赋值，不会写到 state 上；要动 state 就写 `this.xxx = ...`。
7. **`foreground` 目前不会显示**。`FunkinLScript.foreground` 建了一个 `FlxTypedGroup` 并绑成全局，但源码里没有任何地方把它 add 进 state（只有 `FunkinHScript` 那边接了 `foreground`）。要显示 sprite 请 `add(spr)` 或 `this:add(spr)`。
8. **数组下标 1-based**（§5），越界写会 `push` 到数组末尾而不是报错。
9. **类只有静态成员可读**，实例字段请通过对象读写；`IMap` 的字段读写直达 map。
10. **`stop()` 之后再 `call()` 都是 no-op**（`lua == null`）；想让脚本「停一会儿」用 `pauseScript()` / `resumeScript()`，别 stop。
11. `.lscript` 只认 `.lscript` 扩展名——没有 `HScriptUtil.extns` 那套多扩展名匹配。
12. **`inline` / 原生方法经代理表反射调用不一定可用**。代理走的是 `Reflect.getProperty()`，而 hxcpp 下被内联掉的方法（例如 `Math.sin` 这类原生数学函数，或 `ModManager` 里标了 `inline` 的 `getValue` / `getPercent` / `get` / `getVisPos`）在严格 DCE 后可能根本没有可反射的实体。优先调非 inline 的普通方法（如 `modManager:setValue(...)`），数学运算自己用 Luau 的 `math` 库。

---

## 10. 最小示例

```lua
-- mods/<mod>/data/<song>/<song>.lscript
local bg = nil

function onCreate()
	bg = FlxSprite:new(0, 0)
	bg:loadGraphic(Paths.image('menuDesat'))
	bg.screenCenter()
	bg.alpha = 0.6
	add(bg)
	print('LScript ready, bpm =', bpm)
end

function onBeatHit(beat)          -- 用参数，别读全局 curBeat
	if beat % 4 == 0 then
		this.camGame.zoom = 1.02       -- 代理表：读写直达 Haxe（赋值只能写点，不能写冒号）
	end
end

function onStepHit(step)
	if step % 16 == 0 then
		modManager:queueSet(step, 'drunk', 0.5, 0)   -- player 0 = 玩家侧
	end
end

function onUpdatePost(elapsed)
	if bg ~= nil then
		bg.angle = bg.angle + elapsed * 30
	end
end

function onDestroy()
	bg = nil
end
```

可用的辅助探测：`print(...)` 打日志，`import('flixel.FlxSprite', 'Spr')` 临时引入类，`hasFunction('onBeatHit')`（Haxe 侧）检查回调是否存在。
