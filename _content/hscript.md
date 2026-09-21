<!-- source: script/FunkinHScript.hx -->
<!-- source: script/hscript/HScriptUtil.hx -->
<!-- source: script/hscript/HScript.hx -->
<!-- source: script/hscript/InterpPro.hx -->
<!-- source: script/hscript/OScriptState.hx -->
<!-- source: script/GlobalScript.hx -->
<!-- source: script/ScriptDebugOverlay.hx -->
<!-- source: script/Interact.hx -->
<!-- source: FNFGame.hx -->
<!-- source: Main.hx -->
<!-- source: backend/MusicBeatState.hx -->
<!-- source: backend/MusicBeatSubstate.hx -->
<!-- source: states/game/PlayState.hx -->
<!-- source: Project.xml -->

# HScript 脚本 API

> **适用版本：Parker Engine 0.2.8**（`Project.xml` 里的 `<app version>`）。参考工具链：Haxe 4.3.7、HaxeFlixel 5.8.0、`hscript-iris` 1.1.3。
>
> **本文以源码为准。** 每一条 API、回调、路径都是从引擎源码里读出来的；源码里没有的行为本文不会写。凡是「源码里有、但当前版本实际跑不到」的东西，都会明确标注为**未生效**。

HScript 是 Parker Engine 的一等公民：它不是一个外挂层，而是引擎自己的解释器（`script/FunkinHScript.hx` 里同时放着 `HScript`、`Script`、`IFunkinScript`、`ScriptType` 和 `InterpPro`，`script/hscript/HScript.hx` 与 `script/hscript/InterpPro.hx` 只是给旧路径留的 typedef 别名）。

---

## 0. 新手必读（先看这 5 条）

1. **扩展名和位置决定一切**：`.hx` / `.hscript` / `.hsc` / `.hxs` 四种扩展名等价（`HScriptUtil.extns`），文件放对目录就会被自动加载，不需要注册。唯一的例外见 §1.3 的 `scripts/menus/`。
2. **回调 = 同名函数**。脚本里定义 `function onStepHit(step:Int) {}` 就会被调用；没定义的回调会被静默跳过（不会报错）。
3. **`curStep` / `curBeat` 这类全局只在脚本加载那一刻赋值一次**，播放过程中不会再更新（`PlayState` 只更新 Lua 的，HScript 那份写进了一个空数组）。要实时值请用回调参数，或读 `game.curStep`。
4. **`return 'FUNC_STOP'` 并不能真的「中断」其它脚本**：`PlayState.callOnHScripts()` 的 `ignoreStops` 默认是 `true`，所有脚本照样会被调用，只有聚合返回值会变成 `FUNC_STOP`。只有少数调用点（如 `onPause`）会看这个返回值。
5. **出错了先看屏幕左上角**（`PlayState.addTextToDebug`，最多 34 行；Windows 上还会弹一个原生错误框）。脚本状态（自定义状态）里的错误走 `ScriptDebugOverlay`。

---

## 1. 快速开始

### 1.1 HScript 是什么

- 语法是 Haxe 的子集（`crowplexus.hscript` 解析器 + Iris 运行层），支持 `var`、`function`、`if/else`、`for`、`while`、`switch`、`try/catch`、`return`、`import`、以及 Haxe 的对象语法（`obj.field`、`obj.method()`、`new Class(...)`）。
- 一行脚本可以直接访问引擎类（`FlxSprite`、`Paths`、`Character`、`PlayState`…），**不需要写 `import`**，因为它们由 `FunkinHScript.setDefaultVars()` 预先注入为全局变量。
- 脚本顶层代码在 **构造时立即执行**；之后由引擎按名字回调（见 §2）。

### 1.2 最小示例

```haxe
// mods/我的模组/scripts/hello.hx
var text = new FlxText(0, 40, 0, 'Hello Parker Engine', 24);
text.screenCenter();
text.color = 0xFFFFFFFF;

function onCreatePost()
{
	add(text); // 歌曲里 add() 会插到角色组附近，见 §3.6
}

function onStepHit(step:Int)
{
	if (step % 8 == 0)
		text.visible = !text.visible;
}

function onDestroy()
{
	text.destroy();
}
```

### 1.3 脚本放哪里（自动发现规则）

所有路径都先查**当前模组**（`Paths.currentModDirectory`），再查**全局模组**，最后回落到 `mods/` 根目录（`Paths.modFolders()`）；`assets/preload/...` 是内置资源目录。

| 放置位置 | 加载者 | 脚本 `scriptName`（过滤/暂停用） | 说明 |
|---|---|---|---|
| `mods/<mod>/global.hx`（也认 `.hscript`/`.hsc`/`.hxs`） | `Main.initIris()` | `GLOBAL` | 开机时加载一次；`this` 被覆盖成 `Main`，另外给一个 `fnfgame`。只调用 `onCreate`，之后没有任何引擎回调（`Main.onEnterFrame()` 里那句 `scripts.executeAllFunc('onUpdatePost', ...)` 依赖 `Main.scripts`，而引擎从不给它赋值，所以恒定跳过；脚本要持续逻辑就自己挂 `FlxG.stage` 的 `enterFrame`，官方 `global.hx` 示例就是这么做的） |
| `scripts/*.hx`（`mods/<mod>/scripts/` → 全局模组 → `mods/scripts/` → `assets/preload/scripts/`，**递归搜索子目录**） | `PlayState.initScripts()` | 文件名（不含扩展名） | 每首歌都会加载 |
| `data/<格式化歌名>/*.hx`（`mods/<mod>/data/<song>/` → `assets/preload/data/<song>/`，**递归搜索**） | `PlayState.initScripts()` | 文件名 | 只在该首歌加载。歌名要过 `Paths.formatToSongPath()`（小写、空格转 `-`、去标点） |
| `stages/<舞台名>.hx`（先 mods 后 preload） | `PlayState.initScripts()` | 固定为 `stage` | 舞台脚本 |
| `characters/<角色名>.hx`（只查 mods 目录） | `PlayState.initCharScript()` | 角色名 | 角色出现时加载 |
| `custom_notetypes/<音符类型>.hx`（先 mods 后 preload） | `PlayState.loadNoteTypeScripts()` / `startHScriptsOnFolder()` | 音符类型名 | 谱面里出现该类型时加载 |
| `custom_events/<事件名>.hx`（先 mods 后 preload） | `PlayState.startHScriptsOnFolder()` | 事件名 | 谱面里出现该事件时加载 |
| `states/globals/<状态类名>.hx` | `FNFGame.switchState()` → `OScriptState.fromFile()` | 完整文件路径 | 覆盖内置状态，见 §5 |
| `scripts/menus/<状态类名>.<ext>` | `MusicBeatState.setUpScript()` | 文件名 | **当前版本无人调用 `setUpScript()`，未生效**，见 §6 |
| `substates/menu/<名称>.<ext>` | `MusicBeatSubstate.setUpScript()` | 文件名 | 同上，未生效 |

扩展名清单有两个来源，注意差异：

- `HScriptUtil.extns = ["hx", "hscript", "hsc", "hxs"]` —— 上表大部分查找都用它（`PlayState`、`Main`、`FNFGame`、`Macro`）。
- `HScript.exts = ['hx', 'hxs', 'hscript']` —— 只有 `HScript.getPath()` 用（也就是未生效的 `scripts/menus/` 查找），**不含 `hsc`**。

`HScriptUtil.findEncodedScriptsInDir()` 会找 `hxenc` / `hscriptenc` / `hscenc` / `hxsenc`，但引擎里没有任何地方调用它——加密脚本这套目前是死代码。

### 1.4 命名规则

- 脚本文件名（不含扩展名）会成为它的 `scriptName`，用于 `PlayState.setScriptPaused(tag, paused)`、`callOn*` 的 `exclusions` 数组，以及 `HScript.getScriptByTag()`。
- 角色 / 音符类型 / 事件脚本的 `scriptName` 是**角色名、类型名、事件名**本身（不是文件名）。
- 舞台脚本的 `scriptName` 恒为 `'stage'`，因此很难单独暂停某一个舞台脚本。

---

## 2. 脚本生命周期与回调

### 2.1 加载流程（`PlayState` 里实际发生的顺序）

```
PlayState.create()
├─ loadGlobalScripts()           // 只加载 scripts/ 下的 .lua/.lscript/.py（整段在 #if LUA_ALLOWED 里）
├─ initScripts()                 // HScript：scripts/、data/<song>/、stages/<stage>
│   └─ 每个脚本：new HScript(内容, 名字)  ← 脚本顶层代码在这里跑
│                → 若解析失败（parsingException != null）直接丢弃
│                → set('pauseScript' / 'resumeScript' / 'setScriptPaused')
│                → script.call('onCreate')      ← 第一个回调
│                → hscriptArray.push(script)
│                → onAddScript()                ← 注入 curStep/boyfriend/camGame/...
├─ generateSong() → 创建角色、modManager
├─ setDefaultHScripts('modManager', modManager)
├─ loadNoteTypeScripts()
├─ ... super.create() 之前：
│     callOnScripts('onCreatePost')
│     callOnScripts('onLoad')
startSong()
├─ 需要时才加载 custom_notetypes/ 与 custom_events/ 脚本
├─ loadSongScripts(SONG.song)    // data/<song>/ 下的 .lua/.lscript/.py
└─ callOnScripts('onStartCountdown') / onCountdownTick ×N / onSongStart ...

PlayState.destroy()
└─ 每个脚本：hx.call('onDestroy') → hx.stop()
```

要点：

- **`onCreate` 不是引擎统一派发的**，而是 `initIris()` 在构造后手动 `script.call('onCreate')`；所以 `states/globals/` 这类自定义状态里的脚本**收不到** `onCreate`。
- 脚本是**逐个**加载的，每加载一个就重跑一遍 `onAddScript()`：`curStep`/`boyfriend` 之类的注入值用的是「那一刻」的值。
- 脚本在数组里的顺序 = 加载顺序 = `callOnHScripts()` 的调用顺序（先 `assets/preload`，后 mods）。

### 2.2 回调全表（PlayState 向 HScript 派发的）

以下全部是 `PlayState` 通过 `callOnScripts()` / `callOnScriptAll()` 真正会派发到 `hscriptArray` 上的回调。参数写法为「名字: 类型」。

| 回调 | 触发时机 | 参数 | 备注 |
|---|---|---|---|
| `onCreate` | 脚本构造完成、加入数组之前 | 无 | 由 `initIris()` 调用 |
| `onCreatePost` | `PlayState.create()` 里 `super.create()` 之前 | 无 | 和 `onLoad` 紧邻 |
| `onLoad` | 紧接着 `onCreatePost` | 无 | Lua 那边也会收到 |
| `onStartCountdown` | 倒计时开始之前 | 无 | 返回 `FUNC_STOP` 不会阻止倒计时 |
| `preModifierRegister` | `modManager.registerDefaultModifiers()` 之前 | 无 | modchart 用；此时 `modManager` 已经存在 |
| `postModifierRegister` | 内置 modifier 注册完之后 | 无 | 脚本可以在这里注册自己的 modifier |
| `generateModchart` | 每次 `onCountdownTick` 之后 | 无 | 和 `onCountdownTick` 同一个定时器里派发 |
| `onCountdownTick` | 倒计时每次 tick | `swagCounter:Int` | 定时器 `loops = 5`，所以共 5 次：0,1,2,3,4 |
| `onSongStart` | 歌曲正式开始 | 无 | |
| `onUpdate` | 每帧，`super.update()` 之前 | `elapsed:Float` | |
| `onUpdatePost` | 每帧，`update()` 末尾 | `elapsed:Float` | |
| `onStepHit` | 每个 step | `curStep:Int` | 同一步只会触发一次（`lastStepHit` 去重） |
| `onBeatHit` | 每一拍 | `curBeat:Int` | |
| `onSectionHit` | 每一段 | `curSection:Int` | 派发前会把 HScript 的 `curSection` 全局刷新一次 |
| `onUpdateScore` | 分数文本需要刷新时 | `miss:Bool` | |
| `onSpawnNote` | 音符真正进入 `notes` 时 | `note:Note` | Lua 那边收到的是 4 个分散参数，HScript 收整个对象 |
| `goodNoteHit` | 玩家命中 | `note:Note` | |
| `opponentNoteHit` | 对手命中 | `note:Note` | |
| `noteMiss` | 玩家漏按（音符撞线） | `daNote:Note` | |
| `noteMissPress` | 玩家按错键 | `direction:Int` | |
| `popUpScore` | 生成的分数/评级气泡 | `rating:String, comboSpr:FlxSprite, numScore:FlxSprite` | |
| `SkinNoteSplash` | 决定水花皮肤前 | `skin:String` | 传的是字符串副本，改它没用；请返回新的皮肤名 |
| `onEvent` | 谱面事件触发 | `eventName:String, value1:String, value2:String` | |
| `onMoveCamera` | 相机跟随目标变化 | `char:Character` | |
| `onPause` | 打开暂停菜单时 | 无 | `callOnScriptAll('onPause')`，聚合返回值 == `'FUNC_STOP'` 时**不打开**暂停菜单（唯一真正好用的 Stop） |
| `onResume` | 从暂停恢复 | 无 | |
| `onGameOver` | 血量归零、触发死亡 | 无 | 调用点写的是 `ret != Stop \|\| retH != Stop`，单独返回 Stop 拦不住死亡 |
| `onRecalculateRating` | 重算分数/评级 | 无 | 同上，条件也是 `\|\|` |
| `onEndSong` | 歌曲结束（结算前） | 无 | `ignoreStops = false`，但返回值没有被使用 |
| `onDestroy` | `PlayState.destroy()` | 无 | 之后立刻 `stop()`，脚本被销毁 |
| `eventEarlyTrigger` | 计算事件提前量 | `eventName:String, value1:String, value2:String, strumTime:Float` | **返回值会被当成 Float 毫秒数用**：返回数字即可，别返回 `'FUNC_STOP'` 之类 |

只派发给 Lua 的常见回调（HScript / Python **收不到**）：`onKeyPress`、`onKeyRelease`、`onGhostTap`、`onCountdownStarted`、`onCustomSubstate*`、`onGameOverStart`、`onGameOverConfirm`、`onNextDialogue`、`onSkipDialogue`、`onUpdateOptions`、`onEventSet`。

### 2.3 返回值约定：`Function_Stop` / `Function_Continue` / `Function_Halt`

```haxe
// script/GlobalScript.hx
Function_Stop     = 'FUNC_STOP';
Function_Continue = 'FUNC_CONT';
Function_Halt     = 'FUNC_HALT';
```

- 回调**没有 `return`**、或返回 `null`、或函数压根不存在 → `HScript.call()` 一律返回 `Function_Continue`。
- 回调返回其它值 → 这个值会作为「聚合返回值」传给调用方（`eventEarlyTrigger` 就靠这个机制）。
- **`Function_Stop` 在 PlayState 里基本拦不住东西**：`callOnHScripts(event, args, ignoreStops = true)` 只有在 `ignoreStops == false` 时才会 `break`，而 `PlayState` 里几乎所有调用点都用默认值。它真正的效果是让整条调用链的**返回值**变成 `'FUNC_STOP'`。目前只有 `openPauseMenu()` 会检查它。
- **`Function_Halt` 在 PlayState 里没有任何特殊处理**，它和普通返回值一样只会改变聚合返回值。特殊处理在 `MusicBeatState.callOnScript()` / `MusicBeatSubstate.callOnScript()` 里（`Halt` → 变成 `Function_Continue` 并中断），而这两条路径（菜单脚本）当前未被启用。
- 想「跳过其它脚本」目前没有可靠手段；可以改用 `PlayState.setScriptPaused(tag, true)` 暂停自己或别的脚本（见 §3.6）。

---

## 3. 全局 API 参考

这一节把 `FunkinHScript.setDefaultVars()` 注册的**全部**条目、外加 Iris 的 `preset()` 额外注册的 3 个（`Std`、`Math`、`trace`）都列出来：**共 72 个固定条目 + 1 个动态条目**（`Lua_helper.callbacks` 转发，仅有 Lua 时存在）。

`setDefaultVars()` 开头会调用 `_script.preset()`，那是 Iris 自带的最小预置：`Std`、`StringTools`、`Math`、`trace`（`trace` 需要 `#if hscriptPos`，`Project.xml` 里已定义）。

### 3.1 语言 / 标准库 / 宿主

#### `this`
- 当前脚本看到的「自己」，由 `FunkinHScript.getScriptThis()` 决定。**规则见 §4**；歌曲里由 `PlayState` 加载的脚本，`this` 就是 `PlayState.instance`。
- 示例：`this.health -= 0.05;`（歌曲中合法）

#### `script`
- **类型**：`HScript`（`script.FunkinHScript.HScript`）
- 这个脚本包装器本身：`script.scriptName`（文件名/角色名/事件名）、`script.name`、`script.exists('foo')`、`script.executeFunc('foo', [args])`、`script.get('x')` / `script.set('x', v)`、`script.stop()`。
- `defaultVars` 是**静态字段**，请写成 `HScript.defaultVars`（给之后创建的每个 HScript 预置变量）；`PlayState.setDefaultHScripts(name, value)` 就是往它里面写。
- 示例：`if (script.exists('myFunc')) script.executeFunc('myFunc', [1, 2]);`

#### `StringTools`
- **类型**：`StringTools` 类
- 字符串工具（`replace`、`startsWith`、`trim`、`lPad`…）。
- 示例：`var s = StringTools.replace(title, ' ', '-');`

#### `Std`
- **类型**：`Std` 类（来自 Iris `preset()`）
- `Std.int()`、`Std.string()`、`Std.parseInt()`、`Std.random()` 等。
- 示例：`var i = Std.int(elapsed * 60);`

#### `Math`
- **类型**：`Math` 类（来自 Iris `preset()`）
- 标准数学库；另可配合已注册的 `FlxMath`。
- 示例：`var a = Math.sin(Conductor.songPosition / 1000) * 20;`

#### `trace`
- **类型**：函数（来自 Iris `preset()`，需要 `#if hscriptPos`，本项目已定义）
- 会走 Iris 的日志通道：歌曲中打印到屏幕左上角的调试文本（`Iris.print`），日志级别为 `TRACE`。
- 示例：`trace('step ' + step);`

#### `Type`
- **类型**：`Type` 类
- 运行时类型工具。**在默认 API 里缺少某个类时，这是自救的关键**：`Type.resolveClass('flixel.ui.FlxBar')` + `Type.createInstance(cls, [args])`。
- 示例：`var bar = Type.createInstance(Type.resolveClass('flixel.ui.FlxBar'), [0, 0, null, 200, 20]);`

#### `Dynamic`
- **类型**：`Dynamic` 类型
- 动态类型标记，写 `var x:Dynamic = null;` 时可用。

#### `StringMap` / `IntMap` / `ObjectMap`
- **类型**：`haxe.ds.StringMap` / `haxe.ds.IntMap` / `haxe.ds.ObjectMap`
- 三种 Haxe 映射表。注意 HScript 里也支持 `{a: 1}` 这样的匿名结构和 `[]` 数组。
- 示例：`var m = new StringMap(); m.set('a', 1);`

#### `Main`
- **类型**：`Main` 类
- 程序入口类（`Main.fpsVar`、`Main.backPressed` 等静态成员）。`global.hx` 里 `this` 会被覆盖成它。
- 示例：`Main.fpsVar.visible = false;`

#### `Lib`
- **类型**：`openfl.Lib`
- OpenFL 的 `Lib.current` / `Lib.application`。
- 示例：`Lib.application.window.title = 'Parker Engine';`

#### `Assets` / `OpenFlAssets`
- **类型**：`lime.utils.Assets` / `openfl.utils.Assets`
- 底层资源系统。**一般不该用**——请走 `Paths`，否则不认模组。

### 3.2 HaxeFlixel / OpenFL

#### `FlxG`
- **类型**：`flixel.FlxG`
- 全局入口：`FlxG.sound`、`FlxG.camera`、`FlxG.cameras`、`FlxG.keys`、`FlxG.mouse`、`FlxG.random`、`FlxG.save`、`FlxG.width/height`、`FlxG.watch()`。
- 示例：`FlxG.camera.shake(0.02, 0.3);`（签名是 `shake(Intensity, Duration)`，注意强度在前）

#### `FlxSprite`
- **类型**：`flixel.FlxSprite`
- 最常用的精灵类。
- 示例：
  ```haxe
  var spr = new FlxSprite(0, 0).loadGraphic(Paths.image('logo'));
  spr.scale.set(0.5, 0.5);
  spr.updateHitbox();
  add(spr);
  ```

#### `FlxTypedGroup` / `FlxSpriteGroup`
- **类型**：`flixel.group.FlxGroup.FlxTypedGroup` / `flixel.group.FlxSpriteGroup`
- 容器。`FlxSpriteGroup` 有整体位移/缩放语义（`x`、`scale` 作用于整组）。
- 示例：`var grp = new FlxSpriteGroup(); grp.add(spr); add(grp);`

#### `FlxCamera`
- **类型**：`flixel.FlxCamera`
- 相机类。`spr.cameras = [camHUD];` 决定精灵画在哪台相机上。
- 示例：`var cam = new FlxCamera(); cam.bgColor.alpha = 0; FlxG.cameras.add(cam, false);`

#### `FlxMath`
- **类型**：`flixel.math.FlxMath`
- 数值工具：`lerp(a, b, ratio)`、`bound(value, ?min, ?max)`、`inBounds`、`remapToRange`、`distanceBetween(sprA, sprB)`、`distanceToPoint`、`roundDecimal(value, precision)`、`wrap`、`signOf`、`equal`、`fastSin` / `fastCos`。
- 示例：`cam.zoom = FlxMath.lerp(cam.zoom, 1.0, 0.05);`

#### `FlxTimer`
- **类型**：`flixel.util.FlxTimer`
- 定时器。
- 示例：`new FlxTimer().start(0.5, function(t) { spr.alpha = 0; });`

#### `FlxTween` / `FlxEase`
- **类型**：`flixel.tweens.FlxTween` / `flixel.tweens.FlxEase`
- 补间与缓动曲线。
- 示例：`FlxTween.tween(spr, {angle: 360}, 1.0, {ease: FlxEase.quadOut, type: FlxTween.PINGPONG});`

#### `FlxSound`
- **类型**：`flixel.sound.FlxSound`
- 音频对象。
- 示例：`var snd = FlxG.sound.load(Paths.sound('scroll')); snd.play();`

#### `FlxColor`
- **类型**：`script.hscript.HScriptUtil.CustomFlxColor`（不是原版 `FlxColor`）
- 这是一个**静态工具类**：颜色常量（`FlxColor.RED`、`WHITE`、`BLACK`…）与静态函数，函数把颜色当第一个参数。
- 常用：`FlxColor.fromRGB(r,g,b,?a)`、`fromRGBFloat`、`fromString`、`fromHSL`、`fromHSB`、`fromCMYK`、`interpolate`、`gradient`、`getHSBColorWheel`，以及 `toRGBArray(color)`、`lerp(from,to,ratio)`、`toHexString(color)`、`to24Bit(color)`、`getDarkened(color)`、`getInverted(color)`、`getLightened(color)`、`getComplementHarmony(color)` 等。
- 示例：`text.color = FlxColor.fromRGB(255, 120, 0);`

#### `FlxRuntimeShader`
- **类型**：`flixel.addons.display.FlxRuntimeShader`
- 直接 `new FlxRuntimeShader(fragSource, vertSource)` 建 shader（**要的是源码字符串，不是路径**）。更省事的写法是 `Paths.getShader('glitch')`，它帮你读文件、认模组、返回 `null` 表示失败。
- 示例：`spr.shader = Paths.getShader('glitch');`
- 另见 §3.6 的 `newShader()`（当前版本有 bug）与 §3.8 说明的 `ShaderFilter` 未注册问题。

#### `FlxFlicker`
- **类型**：`flixel.effects.FlxFlicker`
- 闪烁效果。
- 示例：`FlxFlicker.flicker(spr, 1, 0.05, true);`

#### `FlxSpriteUtil`
- **类型**：`flixel.util.FlxSpriteUtil`
- 在精灵上画线/画框/填充（`drawLine`、`drawRect`、`fill`、`screenWrap`）。
- 示例：`FlxSpriteUtil.drawRect(spr, 0, 0, 100, 40, 0x88000000);`

#### `FlxBackdrop` / `FlxTiledSprite`
- **类型**：`flixel.addons.display.FlxBackdrop` / `FlxTiledSprite`
- 滚动平铺背景。
- 示例：`var bg = new FlxBackdrop(Paths.image('checker'), FlxAxes.XY, 0.2, 0.2); add(bg);`

#### `FlxCameraFollowStyle`
- **类型**：`flixel.FlxCamera.FlxCameraFollowStyle` 枚举
- 相机跟随样式（`LOCKON`、`PLATFORMER`、`TOPDOWN`、`SCREEN_BY_SCREEN`、`NO_DEAD_ZONE`）。
- 示例：`PlayState.instance.camGame.follow(PlayState.instance.camFollow, FlxCameraFollowStyle.LOCKON);`

#### `FlxTextBorderStyle`
- **类型**：`flixel.text.FlxText.FlxTextBorderStyle` 枚举
- `NONE`、`SHADOW`、`OUTLINE`、`OUTLINE_FAST`。
- 示例：`text.setBorderStyle(FlxTextBorderStyle.OUTLINE, 0xFF000000, 1.5);`

#### `FlxBarFillDirection`
- **类型**：`flixel.ui.FlxBar.FlxBarFillDirection` 枚举
- 血条/进度条填充方向。**注意 `FlxBar` 类本身没有注册**，见 §3.8。

#### `FlxPoint` / `FlxBasePoint`
- **类型**：`flixel.math.FlxPoint.FlxBasePoint`（两个名字指向同一个类）
- 点/向量。
- 示例：`var p = new FlxPoint(0, 0); p.set(50, 50);`

#### `FlxTextAlign`
- **类型**：抽象（由 `MacroPro.buildAbstract()` 从 `FlxText.FlxTextAlign` 生成）
- 取值 `LEFT`、`CENTER`、`RIGHT`、`JUSTIFY`。
- 示例：`text.alignment = FlxTextAlign.CENTER;`

#### `FlxAxes`
- **类型**：抽象（来自 `flixel.util.FlxAxes`）
- 取值 `X`、`Y`、`XY`。

#### `BlendMode`
- **类型**：抽象（来自 `openfl.display.BlendMode`）
- 取值 `ADD`、`MULTIPLY`、`SCREEN`、`INVERT`、`SUBTRACT`…
- 示例：`spr.blend = BlendMode.ADD;`

#### `FlxKey`
- **类型**：抽象（来自 `flixel.input.keyboard.FlxKey`）
- 键码枚举（`FlxG.keys.justPressed.A` 等已直接可用，这个全局用于 `FlxKey.fromString(txt)` 之类场景）。

### 3.3 引擎类

#### `Paths`
- **类型**：`backend.Paths`
- **唯一的资源入口，永远不要硬编码 `assets/...`**。常用：`Paths.image`、`sound`、`music`、`inst`、`voices`、`font`、`video`、`getSparrowAtlas`、`getPackerAtlas`、`getJSONAtlas`、`json`、`txt`、`lua`、`getContent`、`getShader`、`modFolders`、`mods`、`exists`、`formatToSongPath`、`getPreloadPath`、`clearStoredMemory`、`clearUnusedMemory`。
- 示例：`var spr = new FlxSprite().loadGraphic(Paths.image('characters/BOYFRIEND'));`

#### `Conductor`
- **类型**：`backend.songs.Conductor`
- 时间轴：`Conductor.songPosition`（毫秒）、`bpm`、`crochet`、`stepCrochet`、`changeBPM()`、`getBPMFromSeconds()`、`mapBPMChanges()`。
- 示例：`if (Conductor.songPosition > 5000) { /* ... */ }`

#### `Song`
- **类型**：`backend.songs.Song`
- 歌曲数据：`Song.loadFromJson(jsonInput:String, ?folder:String)` 返回 `SwagSong`（谱面对象）——第一个参数是**文件名**（难度后缀也在这里，如 `'bopeebo-hard'`），第二个是歌曲目录名。
- 示例：`var chart = Song.loadFromJson('bopeebo-hard', 'bopeebo'); trace(chart.song);`

#### `ClientPrefs`
- **类型**：`backend.ClientPrefs`
- 全部已保存设置都是 `public static var`：`ClientPrefs.downScroll`、`middleScroll`、`opponentStrums`、`flashing`、`camZooms`、`hideHud`、`noteOffset`、`ghostTapping`、`healthBarAlpha`、`noteSplashes`、`lowQuality`、`globalAntialiasing`、`timeBarType`、`scoreZoom`、`hitsoundVolume`、`pauseMusic` 等。
- 对局相关的开关（血量增减、练习模式、botplay、谱速、modchart 开关等）在 `gameplaySettings` 里，用 **`ClientPrefs.getGameplaySetting(name, defaultValue)`** 读：可用键为 `scrollspeed`、`scrolltype`、`songspeed`、`backbaropacity`、`healthgain`、`healthloss`、`instakill`、`practice`、`botplay`、`opponentplay`、`modchart`。
- **`botPlay` 不是 `ClientPrefs` 的字段**，它是 `PlayState.cpuControlled`（HScript 里写 `game.cpuControlled`）；`ClientPrefs.getGameplaySetting('botplay', false)` 才是那个设置项。
- 示例：`if (!ClientPrefs.flashing) { /* 尊重闪光敏感设置 */ }`

#### `CoolUtil`
- **类型**：`backend.CoolUtil`
- 工具库：`CoolUtil.coolTextFile`、`listFromString`、`getFileStringFromPath`、`findFilesInPath`、`showPopUp`、`boundTo`。

#### `StageData`
- **类型**：`backend.game.StageData`
- 舞台数据（`StageData.getStageFile(name)` 等）。

#### `MusicBeatState`
- **类型**：`backend.MusicBeatState`
- 状态基类：静态 `MusicBeatState.switchState(next)`、`resetState()`、`getState()`、`getVariables()`。
- 注意：**`states.menu.CreditsState` 这种包路径不是全局变量**，直接 `new` 会报 `Unknown variable states`。换状态请先解析类（并注意每个状态的构造参数，例如 `FreeplayState` 需要 `(song, week, songCharacter, color)`）：
  ```haxe
  var cls = Type.resolveClass('states.menu.CreditsState');
  MusicBeatState.switchState(Type.createInstance(cls, []));
  ```
  （`getVariables()` / `getState()` 会 `cast FlxG.state` 成 `MusicBeatState`，从非 MusicBeatState 的状态里调用会失败。）

#### `PlayState`
- **类型**：`states.game.PlayState`
- 游戏状态类本身。`PlayState.instance` 是当前对局实例（没有对局时为 `null`）。**注意：`PlayState` 的 `instance` 是静态字段，脚本里读 `PlayState.instance` 才是安全的写法**；`game` 是它在加载那一刻的快照。

#### `GameOverSubstate`
- **类型**：`substates.game.GameOverSubstate`
- 死亡界面；`GameOverSubstate.instance` 在死亡时可用。

#### `FunkinLua`
- **类型**：`psych.script.FunkinLua`
- Lua 脚本包装器。暴露它主要是为了 `FunkinLua.customFunctions` / `FunkinLua.hscript` 之类的互操作；以及 `createGlobalCallback()` 会用它的静态表（见 §3.5）。

#### `HScript`
- **类型**：`script.FunkinHScript.HScript`
- HScript 包装器类本身，可用来在脚本里新建子脚本：`var s = new HScript(source, 'name');`，或静态的 `HScript.fromString(...)` / `HScript.fromFile(...)` / `HScript.getPath(...)` / `HScript.defaultVars` / `HScript.exts`。

### 3.4 游戏对象

#### `Note`
- **类型**：`obj.Note`
- **构造签名**：`new Note(strumTime:Float, noteData:Int, ?prevNote:Note, ?sustainNote:Bool = false, ?inEditor:Bool = false)`
- 音符对象（`onSpawnNote` / `goodNoteHit` / `noteMiss` 的参数就是它）。常用字段：`noteData`、`noteType`、`strumTime`、`isSustainNote`、`mustPress`、`multAlpha`、`ignoreNote`、`hitCausesMiss`、`noteYPos`；常用方法：`kill()`、`playAnim()`、`resetNote()`。
- 示例：`if (note.noteType == 'Mine') note.hitCausesMiss = false;`

#### `HealthIcon`
- **类型**：`obj.HealthIcon`
- **构造签名**：`new HealthIcon(char:String = 'bf', isPlayer:Bool = false)`（第二个参数必填）
- 血条两侧的角色图标。
- 示例：`var icon = new HealthIcon('dad', false); icon.setGraphicSize(Std.int(150 * 0.7));`

#### `Character`
- **类型**：`obj.Character`
- **构造签名**：`new Character(x:Float, y:Float, ?character:String = 'bf', ?isPlayer:Bool = false)`
- 角色对象（`dad` / `gf` 的类型是 `Character`，`boyfriend` 是它的子类 `Boyfriend`）。
- 示例：`var extra = new Character(0, 0, 'gf'); add(extra);`

#### `NoteSplash`
- **类型**：`obj.NoteSplash`
- **构造签名**：`new NoteSplash(x:Float = 0, y:Float = 0, ?note:Int = 0)`
- **方法签名**：`setupNoteSplash(x:Float, y:Float, note:Int = 0, ?texture:String = null, hueColor:Float = 0, satColor:Float = 0, brtColor:Float = 0)`
- 命中水花（`note` 是 0~3 的方向索引，不是 Note 对象）。**构造函数内部会读 `PlayState.SONG`**，所以不要在歌曲外创建。
- 示例：`var s = new NoteSplash(200, 300, 2); add(s);`

#### `BGSprite`
- **类型**：`obj.BGSprite`
- **构造签名**：`new BGSprite(?image:String, x:Float = 0, y:Float = 0, ?scrollX:Float = 1, ?scrollY:Float = 1, ?animArray:Array<String> = null, ?loop:Bool = false)`
- 背景精灵：给了 `animArray` 就走 `idle` / `danceLeft` / `danceRight` 帧动画，还有 `dance()` 方法。
- 示例：`add(new BGSprite('stageback', -600, -200, 0.9, 0.9, ['idle', 'danceLeft', 'danceRight']));`

#### `StrumNote`
- **类型**：`obj.StrumNote`
- **构造签名**：`new StrumNote(x:Float, y:Float, leData:Int, player:Int)`（**先是方向 `leData`，再是 `player`**）
- 接键。`PlayState` 里的 `playerStrums` / `opponentStrums` 是 `FlxTypedGroup<StrumNote>`。
- 示例：`playerStrums.members[0].x += 10;`

#### `Alphabet`
- **类型**：`obj.Alphabet`（继承 `FlxSpriteGroup`）
- **构造签名**：`new Alphabet(x:Float, y:Float, text:String = "", ?bold:Bool = true)`
- 菜单风格的逐字母文本。改文字用 `alphabet.text = '...'`；`useFlxText` 为 `true` 时退化成单个 `flxText`。
- 示例：`var a = new Alphabet(0, 0, 'HELLO', true); add(a, true);`

#### `AttachedSprite`
- **类型**：`obj.AttachedSprite`
- **构造签名**：`new AttachedSprite(?file:String = null, ?anim:String = null, ?library:String = null, ?loop:Bool = false)`
- 跟随宿主的位置/角度/透明度：把宿主赋给 `sprTracker`，再用 `xAdd` / `yAdd` / `angleAdd` / `alphaMult` / `copyAngle` / `copyAlpha` / `copyVisible` 调。**没有 `add()` 这类挂载方法**，直接 `sprTracker = host;` + 手动 `add(tag)`。
- 示例：
  ```haxe
  var tag = new AttachedSprite('icons/note', null);
  tag.sprTracker = PlayState.instance.healthBar;
  tag.yAdd = 40;
  add(tag, true);
  ```

#### `AttachedText`
- **类型**：`obj.AttachedText`（继承 `Alphabet`）
- **构造签名**：`new AttachedText(text:String = "", ?offsetX:Float = 0, ?offsetY:Float = 0, ?bold = false, ?scale:Float = 1)`
- 跟随宿主的文字；用法同上（`sprTracker` + `offsetX` / `offsetY` / `copyVisible` / `copyAlpha`）。
- 示例：`var lbl = new AttachedText('combo', 0, 40, true, 1); lbl.sprTracker = PlayState.instance.healthBar; add(lbl, true);`

#### `GameOverSubstate`
- **类型**：`substates.game.GameOverSubstate`
- 死亡界面。死亡时 `GameOverSubstate.instance` 可用；`getInstance()` 已经帮你处理了这个分支。
- 示例：`if (PlayState.instance.isDead) trace('dead screen');`

> **`Boyfriend` 不在默认 API 里**：它只在未生效的 `HScriptUtil.setDefaultVars()` 中注册（§3.8）。要用请写 `PlayState.instance.boyfriend` 或 `this.boyfriend`（字段类型就是 `Boyfriend`）。同理 `BackgroundDancer`、`Section`、`WeekData`、`Highscore` 也在那批未生效的名字里。

### 3.5 只有歌曲里（`FlxG.state is PlayState` 且 `PlayState.instance != null`）才注册的

`setDefaultVars()` 里这一批被 `if ((FlxG.state is PlayState) && PlayState.instance != null)` 包着——也就是说，**只有在对局状态下创建的脚本才拿得到**（`global.hx`、菜单脚本、`states/globals/` 脚本都没有）。

#### `game`
- **类型**：`PlayState`
- 当前对局实例。等价于 `PlayState.instance`，但它是加载那一刻取的值。
- 示例：`game.healthBar.createFilledBar(0xFF00FF00, 0xFFFF0000);`

#### `global`
- **类型**：`Map<String, Dynamic>`，就是 `PlayState.variables`
- 跨脚本共享变量的字典。任何脚本都能往里塞东西，别的脚本（包括 Lua）也能通过 `setGlobalFunc`/`callGlobalFunc` 读到。
- 示例：`global.set('myCounter', 0); var n = global.get('myCounter');`

#### `getInstance`
- **类型**：函数 `() -> FlxState`
- **签名**：`getInstance():FlxState`
- 死亡时返回 `GameOverSubstate.instance`，否则返回 `PlayState.instance`。写兼容死亡界面的脚本时用它代替 `PlayState.instance`。
- 示例：`getInstance().add(spr);`

#### `setGlobalFunc`
- **签名**：`setGlobalFunc(name:String, func:Dynamic):Void`
- 把函数塞进共享变量表（等价于 `global.set(name, func)`），Lua 脚本也能通过自定义回调拿到。
- 示例：`setGlobalFunc('myShake', function(power:Float) { PlayState.instance.camGame.shake(power, 0.1); });`

#### `callGlobalFunc`
- **签名**：`callGlobalFunc(name:String, ?args:Dynamic):Dynamic`
- 调用共享变量表里的函数；名字不存在返回 `null`。注意源码里是 `state.variables.get(name)(args)`——**多参数请打包成数组或匿名结构传**。
- 示例：`callGlobalFunc('myShake', 0.02);`

#### `createGlobalCallback`（`#if LUA_ALLOWED`）
- **签名**：`createGlobalCallback(name:String, func:Dynamic):Void`
- 把自己实现的函数注册给**所有 Lua 脚本**（`Lua_helper.add_callback`），同时记进 `FunkinLua.customFunctions`，之后 Lua 侧可以直接按名字调用。
- 示例：`createGlobalCallback('hscriptShake', function(p:Float) { game.camGame.shake(p, 0.1); });`

#### `Lua_helper.callbacks` 里的每一个名字（`#if LUA_ALLOWED`）
- **动态条目**：初始化时会把 Lua 侧已注册的全局回调逐个 `set` 进 HScript 环境，所以 HScript 里通常也能直接叫出 Lua 常用的那些函数名。

### 3.6 函数与特殊全局

#### `add`
- **签名（默认注册）**：`add(obj:FlxBasic):Void`，绑定到 `FlxG.state.add`
- **签名（PlayState 里被覆盖成）**：`add(obj:FlxBasic, ?front:Bool = false):Void`
  - `front == true` → 直接加到状态末尾（画在最上层）；
  - `front == false` → 插到 `dadGroup` / `boyfriendGroup` / `gfGroup` **之前**，也就是风格上「在角色背后」。死亡时会插到死亡界面男友之前。
- 因为 `onAddScript()` 是在脚本创建之后跑的，**只要脚本在 `PlayState` 里加载，就会拿到覆盖版**。
- **注意时序**：脚本体（顶层代码）执行时用的还是默认版 `add`（= `FlxG.state.add`，歌曲里就是 `PlayState.add`，直接追加到末尾）；`onAddScript()` 跑完之后才变成智能插入版。所以顶层代码与回调里的 `add` 行为可能不同。
- 示例：
  ```haxe
  add(bg);            // 角色后面
  add(hud, true);     // 最上层
  ```

#### `remove`
- **签名**：`remove(obj:FlxBasic):Void`
- 状态成员移除。注意它**不会**被 `onAddScript()` 覆盖（只有 `add` 会被覆盖），所以它一直是 `setDefaultVars()` 里绑定的 `FlxG.state.remove` —— 也就是脚本创建时那个状态的 `remove`。歌曲里通常就是 `PlayState` 的，但状态切换脚本里会指向旧状态；要稳妥就写 `game.remove(obj)`。

#### `insert`
- **签名**：`insert(position:Int, obj:FlxBasic):Void`
- 按索引插入到状态的 `members` 里。

#### `members`
- **类型**：`Array<FlxBasic>`
- 当前状态的成员数组（`FlxG.state.members`）。可以用 `members.indexOf(obj)` 反查层级。

#### `foreground`
- **类型**：`FlxTypedGroup<FlxBasic>`
- 每个 HScript 各自拥有的「前景组」，引擎会把它注册成全局，但**不会自动 add 到场景**——想让里面的东西显示，脚本自己要 `add(foreground, true)`。
- 示例：
  ```haxe
  add(foreground, true);
  foreground.add(floatingText);
  ```

#### `newShader`
- **签名**：`newShader(?fragFile:String, ?vertFile:String):FlxRuntimeShader`
- 参数是**文件名**（不带 `.frag`/`.vert`），走 `Paths.modsShaderFragment()` / `Paths.modsShaderVertex()` 找 `shaders/<名字>.frag|.vert`。
- **坑（源码现状）**：函数体里编译出来的 `runtime` 变量没有被返回——无论成败都执行 `return new FlxRuntimeShader();`，也就是说**当前版本 `newShader()` 拿到的永远是空的 shader**。想要真正生效的 shader，请改用引擎里现成的正确实现 **`Paths.getShader(fragFile, vertFile, ?version)`**（它同样走模组感知的 `shaders/` 查找，失败时返回 `null`，并 `trace` 编译错误）。
- 示例：
  ```haxe
  var sh = Paths.getShader('glitch');   // shaders/glitch.frag（+ 可选 .vert）
  if (sh != null)
      spr.shader = new ShaderFilter(sh); // 注意 ShaderFilter 不在默认 API 里，见 §3.8
  ```
  （只想要 shader 对象本身就直接 `spr.shader = Paths.getShader('glitch');`）

#### `pauseScript` / `resumeScript` / `setScriptPaused`
- **签名**（由 `PlayState.initIris()` 注入到每个 HScript 上）：
  - `pauseScript():Bool` —— 暂停自己
  - `resumeScript():Bool` —— 恢复自己
  - `setScriptPaused(tag:String, paused:Bool):Bool` —— 按 `scriptName`（或纯文件名）暂停任意脚本
- 被暂停的脚本**仍然留在数组里、状态不丢**，但引擎不会再给它派发任何回调（`GlobalScript.isScriptPaused()` 会在 `callOnHScripts()` 里 `continue`）。
- 示例：
  ```haxe
  if (onHold) pauseScript(); else resumeScript();
  setScriptPaused('some_other_script', true);
  ```

#### `state`（只有 `OScriptState` 的脚本有）
- **类型**：`OScriptState`
- 被覆盖的那个脚本化状态本身，见 §5。

### 3.7 PlayState 注入的运行时变量（`onAddScript()` / `onAddSScript()`）

这些不是 `setDefaultVars()` 注册的，而是每次加载脚本后由 `PlayState.onAddScript()` 覆盖式写入（`setOnHScripts`）。**共 25 条**，其中 `onAddSScript()`（LScript / Python）有同样的前 21 条。

| 变量 | 类型 | 更新时机 |
|---|---|---|
| `curStep` | `Int` | **仅加载那一刻**（见下方警告） |
| `curBeat` | `Int` | **仅加载那一刻** |
| `curSection` | `Int` | 加载时 + 每次 `sectionHit()` |
| `bpm` | `Float` | 仅加载那一刻（读 `Conductor.bpm`） |
| `camGame` | `FlxCamera` | 加载时（引用不变） |
| `camHUD` | `FlxCamera` | 加载时 |
| `camOther` | `FlxCamera` | 加载时 |
| `camFollow` | `FlxPoint` | 加载时 |
| `camFollowPos` | `FlxObject` | 加载时 |
| `boyfriend` | `Boyfriend` | 加载时（**换角色后引用可能过期**，用 `game.boyfriend` 保险） |
| `dad` | `Character` | 加载时 |
| `gf` | `Character` | 加载时 |
| `boyfriendGroup` / `dadGroup` / `gfGroup` | `FlxSpriteGroup` | 加载时 |
| `notes` | `FlxTypedGroup<Note>` | 加载时 |
| `strumLineNotes` | `FlxTypedGroup<StrumNote>` | 加载时 |
| `playerStrums` / `opponentStrums` | `FlxTypedGroup<StrumNote>` | 加载时 |
| `unspawnNotes` | `Array<Note>` | 加载时（数组引用稳定） |
| `add` | 函数 | 覆盖默认 `add`，见 §3.6 |
| `modManager` | `ModManager` | `PlayState.create()` 里 `setDefaultHScripts('modManager', ...)` |
| `pauseScript` / `resumeScript` / `setScriptPaused` | 函数 | `initIris()` 注入 |

> **警告：`curStep` 与 `curBeat` 不会随歌曲更新。** `PlayState.stepHit()` 里只有 `setOnLuas('curStep', curStep)`（Lua）和 `scripts.setAll('curStep', curStep)`（`scripts` 是一个**始终为空**的 `FunkinHScript` 组），HScript 数组没有被更新。所以：
> - 想在每个 step 里用实时步数，请用 `onStepHit(step)` 的参数；
> - 想读实时值，用 `game.curStep` / `PlayState.instance.curStep`（HScript 的字段访问走运行时反射，不检查 private）；
> - 或自己维护一个变量：`var myStep = 0; function onStepHit(s:Int) { myStep = s; }`。

### 3.8 `HScriptUtil` 里注册、但**当前版本不生效**的 API

`script/hscript/HScriptUtil.hx` 里有一个 `override function setDefaultVars()`，它会在 `FunkinHScript.setDefaultVars()` 的基础上**再注册一大批**类（`Std`、`Type`、`Reflect`、`Math`、`Json`、`FileSystem`、`File`、`Sys`、`Capabilities`、`ShaderFitler`、`FlxBar`、`FlxGraphic`、`FlxBasic`、`FlxObject`、`FlxText`、`FlxTextFormat`、`FlxShader`、`FlxVideo`、`FlxVideoSprite`、`PsychVideoSprite`、`ParkerVideoSprite`、`Handle`、`ModManager`、`Modifier`、`SubModifier`、`NoteModifier`、`EventTimeline`、各种 `*Event`、`WeekData`、`Highscore`、`Boyfriend`、`BackgroundDancer`、`Section`，以及函数 `addBehindGF` / `addBehindBF` / `addBehindDad`、`fromRGB`、`colorFromString`、`runLuaCode`、若干 `LEFT_TO_RIGHT` 之类的常量）。

**但是：`HScriptUtil` 从来没有被实例化过。** 引擎里所有用到它的地方都只碰它的**静态成员**（`HScriptUtil.extns`、`HScriptUtil.findScriptsInDir()`、`HScriptUtil.findEncodedScriptsInDir()`，以及 `FlxColor` 指向的 `HScriptUtil.CustomFlxColor`）；`PlayState.initIris()` 里写的是 `new HScript(...)`，解析到的是 `FunkinHScript.HScript`，它的 `setDefaultVars()` 直接调用 `FunkinHScript.setDefaultVars()`，不会走到子类的 override。

结论：**上面这批名字在 0.2.8 里拿不到**（比如 `Reflect`、`Sys`、`FlxBar`、`ModManager`、`addBehindGF`）。要替代它们：

- 用 `Type.resolveClass()` / `Type.createInstance()` 拿类（`Type` 是注册过的，见 §3.1）；
- 或者直接 `import`（见 §3.9）；
- `FlxColor` 的常量与工具函数是可用的（`CustomFlxColor` 被显式注册了）。

### 3.9 自救：用 `import` 或 `Type` 拿到任意类

HScript 支持 `import` 语句，解析走 `Type.resolveClass()` / `Type.resolveEnum()`（`crowplexus.hscript.Tools.getClass`），且默认没有黑名单：

```haxe
import flixel.ui.FlxBar;
// 也可以 import 内部类型，例如 flixel.text.FlxText.FlxTextBorderStyle

// FlxBarFillDirection 是注册过的全局（实际是个 Haxe enum，见 §3.2）
var bar = new FlxBar(0, 0, FlxBarFillDirection.LEFT_TO_RIGHT, 200, 20);
bar.createFilledBar(0xFF000000, 0xFFFF0000);
add(bar, true);
```

运行时反射的写法（`Type.createInstance` 的参数是数组；不确定的枚举参数传 `null` 用默认值）：

```haxe
var cls = Type.resolveClass('flixel.ui.FlxBar');
var bar = Type.createInstance(cls, [0, 0, null, 200, 20]);
add(bar, true);
```

---

## 4. `this` 的解析规则

源码：`FunkinHScript.getScriptThis()` + `InterpPro` 构造与 `resolve()`。

```
1. 解释器的 parent（InterpPro.parent），若不为 null 就用它
2. 否则 PlayState.instance（若不为 null）
3. 否则 FlxG.state
```

而 `HScript` 的构造函数里是 `_script.interp = new InterpPro(FlxG.state)`，所以第 1 步几乎总能命中，实际含义是：

| 脚本在哪里创建 | `this` 是谁 |
|---|---|
| `PlayState` 加载的游戏脚本（`scripts/`、`data/<song>/`、角色、音符类型、事件、舞台） | 就是当时的状态 —— 歌曲中即 `PlayState.instance` |
| `Main` 加载的 `global.hx` | 被 `Main.onAddScript()` 覆盖成 `Main` 类（静态成员，常见用法：`Main.fpsVar`） |
| `FNFGame.switchState()` 里创建的 `states/globals/*.hx` | **上一个状态**（切换还没发生，`FlxG.state` 仍是旧状态）；这类脚本应该用 `state` 全局 |
| `MusicBeatState.setUpScript()`（未生效） | 当时的状态 |

**额外作用**：`InterpPro` 还重写了 `resolve()` / `assign()` / `evalAssignOp()`，让**没有声明的裸标识符**去 `parent` 的字段里找：

```haxe
// 歌曲里，即使脚本没声明过 these，也能直接读到 parent（PlayState）的字段：
camHUD.zoom = 1.2;          // 注意：camHUD 本身是注入的全局
PlayState.instance.boyfriend.alpha = 0.5;
```

赋值时若该名字不在脚本变量表里、却是 parent 的字段，会直接写回 parent（这就是 `this.xxx = 1` 与 `xxx = 1` 都能生效的原因）。优先级是：**局部变量 → 脚本变量/全局 → import → parent 字段**。

`InterpPro` 还改写了 `fcall()`：函数不存在时报 Iris 错误并返回 `null`，而不是让整个虚拟机崩掉。

---

## 5. HScript 自定义状态（`states/globals/`）

### 5.1 钩子在哪

`FNFGame.switchState()`（`source/FNFGame.hx`）在任何 `MusicBeatState` 切换生效之前检查：

```haxe
if (_nextState is MusicBeatState && state.canBeScripted) {
    simpleName = 类名（不含包名）;
    for (extn in HScriptUtil.extns)          // hx, hscript, hsc, hxs
        if (Paths.exists(Paths.modFolders('states/globals/$simpleName.$extn')))
            → _nextState = OScriptState.fromFile(path);      // HScript 胜出
    else if (states/$simpleName.lua 存在)     → new LuaSState($simpleName);      // #if LUA_ALLOWED && MODS_ALLOWED
    else if (states/$simpleName.lscript 存在) → new LScriptSState($simpleName);
}
```

- 优先级：**HScript > Lua > LScript**。
- 覆盖对象：任何 `canBeScripted == true` 的 `MusicBeatState`。`MusicBeatState` 的构造函数是 `new(canBeScripted:Bool = true)`，**只要子类没显式传 `false`（`super(false)`），它就是可覆盖的**——`TitleState`、`MainMenuState`、`StoryMenuState`、`PlayState` 都没有自己的构造函数（走默认值 `true`），`FreeplayState` 虽然有自己的构造函数（`new(song, week, songCharacter, color)`）但也没传 `false`。源码里显式传 `false` 的只有 `LuaSState` 和 `LScriptSState`。想要拒绝覆盖，在类上加 `@:noScripting`（`Macro.addScriptingCallbacks()` 会生成 `get_canBeScripted() => false`）——不过该宏当前没有被任何类使用，需要自己接线。
- `FNFGame.switchState()` 还会做两件补丁工作：第一次切换时先 `WeekData.loadTheFirstEnabledMod()`，并补做 `TitleState.create()` 里那一套启动初始化（`PlayerSettings.init()`、存档 `bind`、`ClientPrefs.loadPrefs()`、`Paths.pushGlobalMods()`、Android 的 `MobileData.init()`）。**这是为了让第一个被脚本覆盖的状态里 `PlayerSettings.player1` 不是 null**。

### 5.2 `OScriptState` 提供的全局

`OScriptState.loadScript()` 在脚本（顶层代码已执行完）之后，依次注入：

| 全局 | 说明 |
|---|---|
| `state` | 这个 `OScriptState` 自己 |
| `add` / `remove` / `insert` / `members` | 该状态的 `add` / `remove` / `insert` 方法与 `members` 数组 |
| `addTouchPad` / `addPadCamera` | 仅 `#if android` |
| `pauseScript` / `resumeScript` | 暂停/恢复这个脚本 |

另外它会先调用一次 `customMenu()`：

```haxe
customMenu = hscript.call('customMenu', []);   // 返回值存在 OScriptState.customMenu 上
```

`customMenu` 的语义（原意）是「这个脚本是否完全自绘菜单」，调用方 `isHardcodedState()` 读它——**但 `isHardcodedState()` 全项目没有任何调用者**。

### 5.3 现状（重要，读源码得出的结论）

`OScriptState` **只做两件事**：执行脚本体、调用 `customMenu`。它**没有** `update` / `stepHit` / `beatHit` / `destroy` 的脚本派发，也**没有**调用 `onCreate`。真正派发 `onCreate` / `onUpdate` / `onStepHit` 的代码在 `MusicBeatState.setUpScript()` 里，而**当前源码中没有任何状态调用 `setUpScript()`**。

同时注意时序：**脚本体是在 `hscript.set('state'/'add'/'remove'/'insert'/'members', ...)` 之前执行的**（脚本体在 `new HScript(...)` 里跑），而 `customMenu` 也在这些绑定之前被调用。所以：

- 脚本体执行时，`add()` 还是 `setDefaultVars()` 里绑定到**旧状态**的 `FlxG.state.add`；
- `state` / 该状态自己的 `add` 只有在绑定时才存在，而那时脚本已经跑完、`customMenu` 也已调用完毕；
- 脚本能用的其他东西：`PlayState.instance`（如果切换发生在对局中则非 null）、`FlxG`、以及任何已注册的引擎类。

因此 `states/globals/<StateName>.hx` 在 0.2.8 里应当被当作**实验性/半成品**：钩子是真的（会被加载、会替换状态），但「状态里持续跑脚本回调」这件事没有接线。想真的用它，需要脚本自己在顶层代码里接管（例如对 `FlxG.stage` 挂 `enterFrame` 监听、或把逻辑塞进 `customMenu`），并接受 `add` 指向旧状态的事实。

---

## 6. 其他脚本化位置

| 机制 | 位置 | 现状 |
|---|---|---|
| 菜单状态脚本 | `MusicBeatState.setUpScript(s)` → `HScript.getPath('scripts/menus/' + s)`（扩展名只有 `hx/hxs/hscript`） | 实现完整（`onCreate`、`onUpdate`、`onStepHit`、`onDestroy` 都有派发），但**没有任何状态调用它** |
| 子状态脚本 | `MusicBeatSubstate.setUpScript(s)` → `substates/menu/<s>.<ext>`，额外注入 `add`/`close`/`this` | 同上，**无人调用** |
| Lua 状态脚本 | `states/<StateName>.lua` → `LuaSState` | 已接线，且是三个里回调最全的（`onCreate`/`onCreatePost`/`onUpdate`/`onUpdateOptions`/`onUpdatePost`/`onBeatHit`/`onStepHit`/`onEventSet`/`onDestroy`/`onDestroyPost`） |
| LScript 状态脚本 | `states/<StateName>.lscript` → `LScriptSState` | 已接线（`onLoad`/`onCreatePost`/`onUpdate`/`onUpdatePost`/`onBeatHit`/`onStepHit`/`onDestroy`…） |

---

## 7. 错误查看与调试

### 7.1 对局中

- Iris 的日志（`trace`、`Iris.warn`、`Iris.error`）被 `HScript.InitLogger()` 重定向到 `PlayState.addTextToDebug()`：**屏幕左上角**，白/黄/红三色，**最多 34 行**，每行 6 秒后淡出。
- `HScript.error()` 还会弹一个阻断式对话框：Windows 上是 `CPPInterface.messageBox()`，其他平台是 `CoolUtil.showPopUp()`；**同一个脚本只会弹一次**（内部 `alreadyShownError`），并且会附上出错行号（`getCurLine()` 读 `interp.posInfos().lineNumber`）。
- 解析错误（语法错）会在 `tryExecute()` 里被抓住，写进 `parsingException`，并且 `PlayState.initIris()` 会**直接丢弃**这个脚本（`stop()` 后不加入数组）。屏幕上会看到 `[脚本名]: PARSING ERROR: ...`。
- `addTextToDebug()` 整体在 `#if LUA_ALLOWED` 里——如果构建没有开 `LUA_ALLOWED`，这套屏幕日志不存在（而 HScript 的日志代码是按原样调用它的）。

### 7.2 脚本状态里（没有 PlayState 时）

- `script/ScriptDebugOverlay.hx` 是给 `LuaSState` / `LScriptSState` / `OScriptState` 用的共屏覆盖层：`ScriptDebugOverlay.attach(state)` 在各状态 `create()` 里挂载，`report(text, color)` 是统一入口。
- 规则：**有 PlayState 就转给 `PlayState.addTextToDebug()`**；没有就画在自己的覆盖层上（同样最多 34 行、6 秒淡出）。
- 覆盖层用自己的 `FlxCamera`，并且每帧把自己重新排到 `FlxG.cameras.list` 的最后（`keepOnTop()`），保证压在所有精灵、子状态和模组相机之上。
- 在覆盖层还不存在时（构造期间）报的消息会先排队，等 `attach()` 时一次性刷出。
- `OScriptState` 会在建好脚本后调用 `ScriptDebugOverlay.hookScriptLog()`，把 Iris 的 `warn/error/print` 接到覆盖层——否则 Iris 的错误处理会去访问不存在的 `PlayState.instance` 而二次崩溃。

### 7.3 调试技巧

- 用 `trace()` 而不是 `FlxG.log`，能看到屏幕。
- `script.debugPrint()` → **不存在**（`Script` 基类里叫 `scriptTrace()`，且 `HScript` 没有覆写它）。
- 想看解析结果：`HScript.parsingException`。
- 脚本中途停掉自己：`script.stop()`。

---

## 8. 引擎特性速查（与脚本相关）

| 特性 | 文件 | 状态 |
|---|---|---|
| HScript 引擎本体（`HScript`/`Script`/`IFunkinScript`/`ScriptType`/`InterpPro`） | `script/FunkinHScript.hx` | 在用 |
| 旧路径别名（`script.hscript.HScript` 等 typedef） | `script/hscript/HScript.hx`、`InterpPro.hx` | 在用（只是别名） |
| 全局 API 的补充列表 | `script/hscript/HScriptUtil.hx` | **只有静态成员在用**，`setDefaultVars()` override 未生效（§3.8） |
| 脚本返回值常量（`FUNC_STOP`/`FUNC_CONT`/`FUNC_HALT`）、脚本暂停注册表 | `script/GlobalScript.hx` | 在用（`Function_Stop`/`Continue` 还注册给了 Python） |
| 脚本化状态替换 | `FNFGame.switchState()` + `script/hscript/OScriptState.hx` | 钩子在用，回调派发未接线（§5.3） |
| 脚本错误覆盖层 | `script/ScriptDebugOverlay.hx` | 在用（Lua/LScript/OScriptState） |
| 双向变量绑定 `Interact` | `script/Interact.hx` | **未接线**：`Interact` 全项目没有任何引用，且它引用的 `HScript._interp` / `HScript.variables` 在当前 `FunkinHScript.HScript` 上已不存在（字段改名为 `_script`），文件属于历史遗留 |
| `Macro.addScriptingCallbacks()` 构建宏 | `script/Macro.hx` | **未使用**：没有任何类带 `@:build(script.Macro...)`；宏内部还会去扫描 `mods/<folder>/global/<ClassName>.<ext>`（`folder` 默认 `'states'`）并 `new FunkinHScript()`，而 `FunkinHScript.initScript()` 读了文件内容却没有真的创建脚本，整条路径不完整 |
| `MacroState.buildScriptedState()` | `script/hscript/MacroState.hx` | **未使用**（源码注释就写着 `NOT DONE`），类名在源码里也拼成了 `MarcoState` |
| `HScriptModifier`（用 HScript 写 modchart modifier） | `modchart/HScriptModifier.hx` | **未接线**：无任何引用，且它调用的 `script.exitsVar()` / `FunkinHScript.addScript()` 在当前代码里不存在。脚本自定义 modifier 目前请走 `preModifierRegister` / `postModifierRegister` 回调 + `modManager`（`modManager` 是注册过的全局） |
| 加密脚本（`hxenc` 等） | `HScriptUtil.findEncodedScriptsInDir()` | 无调用者 |

---

## 9. 常见坑清单

1. **`curStep` / `curBeat` 全局是「加载时快照」**，不是实时值（§3.7）。用回调参数或 `game.curStep`。
2. **`return 'FUNC_STOP'` 几乎拦不住东西**（§2.3）：默认 `ignoreStops = true`，其它脚本照跑。真正会看它的是 `onPause`。
3. **别在 `eventEarlyTrigger` 里返回非数字**：返回值会被 `cast` 成 Float 当作提前毫秒数。
4. **脚本数组里的顺序 = 加载顺序，且加载顺序是「先内置后模组」**：想覆盖别人的行为，靠 `exclusions` 或暂停机制，而不是靠「后加载的赢」。
5. **`this` 在状态覆盖脚本里是「上一个状态」**（§4），`add` 也被绑到它身上。要操作被覆盖的状态，等 `state` 绑定（但你收不到回调，见 §5.3）。
6. **`foreground` 不会自动上屏**：要自己 `add(foreground, true)`。
7. **`newShader()` 当前返回空 shader**（§3.6 的坑），请改用 `Paths.getShader('名字')`（它帮你在 `shaders/` 里按模组顺序找 `.frag`/`.vert` 并编译，失败返回 `null`）。
8. **`HScriptUtil` 那一大批「应该有的」类其实没注册**（§3.8）：`Reflect`、`Sys`、`FlxBar`、`ModManager`、`addBehindGF` 等都得靠 `import` 或 `Type.resolveClass()` 绕过去。
9. **`hsc` 扩展名有一个例外**：`HScript.getPath()`（菜单脚本查找）只认 `hx/hxs/hscript`。
10. **`scripts/` 与 `data/<song>/` 是递归搜索的**，子目录里的 `.hx` 也会被加载，`scriptName` 只取文件名。
11. **全局脚本 `scripts/` 里的 `.py` 需要 `LUA_ALLOWED`**：`PlayState.loadGlobalScripts()` 整个函数体都在 `#if LUA_ALLOWED` 内（HScript 不受影响，它走 `initScripts()`）。
12. **脚本暂停是「停派发」，不是「停自己已经起飞的定时器/补间」**：`pauseScript()` 只让引擎不再调用它。
13. **覆盖「第一个状态」时，引擎已经替你补过启动初始化**（`FNFGame.ensureBootInit()`：`PlayerSettings.init()`、存档 `bind`、`ClientPrefs.loadPrefs()`、`Paths.pushGlobalMods()`、Android `MobileData.init()`）。不要假设其它「开机一定会跑」的东西也跑过了——`TitleState.create()` 里的其余初始化不会替你执行。
14. **`FlxColor` 不是原版 `FlxColor`**：它是 `CustomFlxColor`，颜色是函数的第一个参数（`FlxColor.toHexString(color)`），常量写法 `FlxColor.RED` 正常。
15. **写脚本请遵守引擎的目录约定**（与 `Paths` 一致）：不要把 `.hx` 塞进 `characters/` 以外的地方指望它被角色加载，各目录的加载者是写死的（§1.3）。
