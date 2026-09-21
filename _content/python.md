<!-- source: script/FunkinPython.hx -->
<!-- source: script/GlobalScript.hx -->
<!-- source: states/game/PlayState.hx -->
<!-- source: Project.xml -->
<!-- source: script/FunkinHScript.hx -->
<!-- external: pyscript (haxelib, git main) PScript.hx / core/Interpreter.hx -->

# Python 脚本 API

> **适用版本：Parker Engine 0.2.8**（`Project.xml`）。运行层是 `pyscript` haxelib（`PScript` + `pyscript.core.Interpreter`，一个用 Haxe 写的 Python 解释器子集），包装类是 `script/FunkinPython.hx`。
>
> **本文以源码为准。** 下面每条 API、每个回调名都是从 `FunkinPython` / `PlayState` 源码里读出来的；`pyscript` 的行为以本地 haxelib 源码为准。凡是「有代码但没接线」的都标注为**未生效**。

---

## 0. 结论先行：Python 支持度总览

| 维度 | 结论 |
|---|---|
| 是否可用 | **可用**，但只在 `#if PYTHON_ALLOWED`（`Project.xml`：`desktop \|\| android`）的构建里 |
| 扩展名 | `.py` 唯一 |
| 自动发现位置 | 5 处：`scripts/`（受 `#if LUA_ALLOWED` 限制）、`data/<格式化歌名>/`、`stages/<舞台>.py`、`custom_notetypes/<类型>.py`、`custom_events/<事件>.py` |
| 引擎回调 | 与 HScript **同一套**（`PlayState.callOnScripts()` 会把事件同时派发给 `callOnPScripts()`），但只限 PlayState 里派发的那些；脚本状态（`states/*.lua` 那一类）不支持 Python |
| 状态覆盖 | **不支持**。`FNFGame.switchState()` 只认 `.hx/.hscript/.hsc/.hxs`、`.lua`、`.lscript`，没有 `.py` |
| 暴露的全局 | **65 个**（含 4 个仅对局的，见 §3），另外 `onAddSScript()` 还会注入 20 个对局变量（§3.8） |
| `this` 绑定 | **没有**。Python 没有 `this`；父对象要自己用 `script.parent`（有时序限制，见 §7）或 `game` |
| 生命周期 | 顶层代码 → `onCreate` → PlayState 各回调 → `onDestroy` |
| 返回值 | 支持返回 `Function_Stop` / `Function_Continue` / `Function_Halt` 常量；语义与 HScript 相同（见 §5） |
| 暂停/恢复 | 支持 `pauseScript()` / `resumeScript()` / `setScriptPaused(tag, paused)` |
| 错误显示 | 有：走 `PlayState.addTextToDebug()`（因此同样依赖 `LUA_ALLOWED`），打印不存在的回调不会报错（静默跳过） |
| 与 HScript 的差距 | 没有 `this`、没有 `state`、没有 `newShader`、没有 `FlxColor`、没有 `FlxBar` / `ModManager` / `Modifier` / `CoolUtil` / `MusicBeatState` / `BGSprite` / `Alphabet` 等一大批类、没有 `HScriptUtil` 那批补充 API、没有自定义状态 |

一句话总结：**Python 在本引擎里是「能跑、能收全部游戏回调、但 API 面只有 HScript 一半」的第二梯队脚本语言**。写复杂功能的建议仍然是 HScript 或 Lua；Python 适合轻量逻辑，或者从其它提供 Python 脚本支持的引擎迁过来的脚本。

---

## 1. 加载方式与自动发现

`PlayState.initPScript(filePath)` 是唯一的入口：

```haxe
function initPScript(filePath:String)
{
    var script:FunkinPython = new FunkinPython(filePath); // ① 读文件、建解释器、注入全局
    pscriptArray.push(script);                           // ② 进入 Python 脚本数组
    onAddSScript();                                      // ③ 注入 curStep/camHUD/boyfriend/... （见 §3.8）
    script.execute();                                    // ④ 跑顶层代码，然后调用 onCreate
    script.setParent(this);                              // ⑤ 之后才把 parent 设成 PlayState
    return script;
}
```

`.py` 的自动发现位置（`Paths.modFolders()` 模组优先，然后 `assets/preload/...` 内置）：

| 位置 | 触发时机 | 备注 |
|---|---|---|
| `scripts/*.py`（模组 → 全局模组 → `mods/scripts/` → `assets/preload/scripts/`，**不递归**，只看目录第一层） | `PlayState.create()` → `loadGlobalScripts()` | **整段代码在 `#if LUA_ALLOWED` 里**：构建没开 `LUA_ALLOWED` 时这些 Python 脚本不会被加载 |
| `data/<格式化歌名>/*.py` | `startSong()` → `loadSongScripts(SONG.song)` | 不在 `#if LUA_ALLOWED` 内，但同样**不递归子目录**（用 `FileSystem.readDirectory`） |
| `stages/<舞台名>.py` | `PlayState.create()` | 走 `startPyOnFolder()`；舞台名来自谱面 `stage` 字段 |
| `custom_notetypes/<音符类型>.py` | `startSong()` | 谱面里出现该音符类型时加载；先查模组再查 `assets/preload` |
| `custom_events/<事件名>.py` | `startSong()` | 谱面里出现该事件时加载；先查模组再查 `assets/preload` |

`PlayState` 还提供一个公开方法，模组脚本可以调用它动态加载：

```haxe
PlayState.instance.startPyOnFolder('data/mysong/extra.py');  // 已加载过同名则返回 false
```

**没有** 的位置：`characters/*.py`（角色脚本只认 HScript）、`states/*.py`（状态覆盖不认 Python）、`global.py`（开机全局脚本不支持，只有 `global.hx` 那套）。

`scriptName` 就是传给 `FunkinPython` 的路径（`scriptName = script`），用于 `setScriptPaused(tag, ...)` 匹配 —— `GlobalScript.scriptMatchesTag()` 会同时接受完整路径和纯文件名。

---

## 2. 包装类 `FunkinPython` 的工作方式

```haxe
class FunkinPython extends FlxBasic
{
    public var PyScript:PScript;
    public var scriptName(default, null):String;
    public static final defaultVars:Map<String, Dynamic> = new Map<String, Dynamic>();
    public var foreground:FlxTypedGroup<FlxBasic>;
}
```

- **构造**：如果路径存在就读文件内容，否则把传入字符串当成内联代码（`new FunkinPython('print("hi")')` 在 Haxe 侧可用）。
- **颜色语法改写**：`applyColorWorkarounds()` 会把 `FlxColor.fromRGB(` → `FlxColor().setRGB(`、`fromRGBFloat` / `fromHSV` / `fromHSB` / `fromCMYK` 同理。**注意 `FlxColor` 本身没有注册成 Python 全局**（见 §3），所以这套改写买不到什么。
- **`defaultVars`**：静态表，构造时会逐个 `set`。引擎里**从不填写它**——`PlayState.setDefaultPScripts()` 存在但没有任何调用者。想给所有后续 Python 脚本预置变量，需要自己调用（例如从 HScript 里 `Type.resolveClass('script.FunkinPython').defaultVars.set(...)`）。
- **`execute()`**：`PyScript.execute()` 跑顶层代码，然后 `call('onCreate')`。
- **`set` / `get`**：`PyScript.setVar()` / `getVar()`，可在 Haxe 侧读写脚本变量。
- **`setClass(cls)`**：按类名（不含包名）注册一个 Haxe 类给脚本用，引擎内部没用它。
- **`stop()`**：`closed = true` 且 `PyScript.interpreter = null`；此后所有 `call`/`set`/`get` 直接返回/忽略。
- **`setParent(obj)`**：设置 `PyScript.parent`，也就是脚本里能读到的 `script.parent`。
- **`foreground`**：与 HScript 一样，每个脚本一个「前景组」，注册成全局 `foreground`，但**引擎不会把它 add 到场景**，脚本要自己 `game.add(foreground)`。

`#if PYTHON_ALLOWED` 未定义时（如 HTML5 构建）：构造函数只做一件事——往调试文本打一条黄色提示 `PYTHON support is disabled. Script functionality is limited.`，其它方法全部空实现。（顺带一提：该 `#else` 分支里用到的 `haxe.io.Path` 只在 `#if PYTHON_ALLOWED` 块中被 `import`，这条分支能否通过编译没有验证。）

---

## 3. 暴露的 Python 全局（完整列表）

以下全部来自 `FunkinPython.setupPythonEnvironment()`（`FunkinPython.hx`）。**共 65 条**（`#if sys` 的三条在 desktop/android 上都在；把 `sys` 相关的三条去掉是 62 条）。

### 3.1 返回值常量

| 名字 | 值 | 说明 |
|---|---|---|
| `Function_Stop` | `'FUNC_STOP'` | 与 HScript/Lua 同一个常量（来自 `GlobalScript`） |
| `Function_Continue` | `'FUNC_CONT'` | 默认返回值 |
| `Function_Halt` | `'FUNC_HALT'` | |

### 3.2 Flixel / OpenFL

`FlxG`、`FlxSprite`、`FlxGraphic`、`FlxBasic`、`FlxObject`、`FlxCamera`、`FlxSpriteGroup`、`FlxTypedGroup`、`FlxTween`、`FlxEase`、`FlxTimer`、`FlxSound`、`FlxText`、`FlxTextFormat`、`FlxShader`、`FlxRuntimeShader`、`ShaderFilter`、`FlxAxes`（对象，含 `X`/`Y`/`XY`）、`BlendMode`（对象，含 `ADD`/`MULTIPLY`/`SCREEN`/`INVERT`…）、`Lib`、`Capabilities`。

- **`FlxAxes` / `BlendMode` 注入的是匿名对象**（源码里写的是 `{"X": FlxAxes.X, ...}` / `{"ADD": BlendMode.ADD, ...}`），不是 Haxe 枚举类。底层值分别是 Int（`X=1`、`Y=16`、`XY=17`）和 String（`ADD="add"`、`MULTIPLY="multiply"`…），所以就算对象属性能不能读通，也可以直接用底层值：`spr.blend = "add"`、背景滚动写 `17`。
- **没有** `FlxBar`、`FlxBackdrop`、`FlxTiledSprite`、`FlxFlicker`、`FlxSpriteUtil`、`FlxMath`、`FlxPoint`、`FlxKey`、`FlxColor`、`FlxCameraFollowStyle`、`FlxTextBorderStyle`、`FlxBarFillDirection`。

### 3.3 视频

`FlxVideo`、`FlxVideoSprite`、`PsychVideoSprite`、`ParkerVideoSprite`（=`PsychVideoSprite` 的别名）、`Handle`（hxvlc 的句柄工具）。

### 3.4 标准库 / 互操作

`Std`、`Type`、`Reflect`、`Math`、`StringTools`、`Json`（对象，含 `parse` / `stringify`）；`#if sys` 下还有 `FileSystem`、`File`、`Sys`。

- `Type.resolveClass()` + `Type.createInstance()` 是**在 Python 里拿到未注册类的主要办法**（例如 `Type.resolveClass("flixel.ui.FlxBar")`）。
- Python 本身自带内置函数（`print`、`len`、`str`、`int`、`float`、`bool`、`list`、`dict`、`range`、`sum`、`max`、`min`、`abs`、`round`、`pow`、`type`、`isinstance`、`chr`、`ord`、`hex`、`oct`、`bin`、`super`），由解释器直接提供。
- `print` 的输出经 `PyScript.onPrint` → `PlayState.addTextToDebug('脚本名:行号: 内容', 白色)`，也就是**打在游戏屏幕左上角**（依赖 `LUA_ALLOWED`）。

### 3.5 引擎类

`PlayState`、`game`、`Paths`、`ClientPrefs`、`WeekData`、`Highscore`、`StageData`、`Song`、`Section`、`Conductor`、`Note`、`StrumNote`、`NoteSplash`、`Character`、`Boyfriend`。

- **`game`**：`PlayState.instance` 的**构造时快照**（可能为 `null`，例如在没有对局的状态下创建脚本——实际加载路径都在对局里，所以正常可用）。
- **没有** `CoolUtil`、`MusicBeatState`、`HScript`、`FunkinLua`、`GameOverSubstate`、`ModManager`、`Modifier`、`BGSprite`、`Alphabet`、`HealthIcon`、`AttachedSprite`、`AttachedText`、`BackgroundDancer`。

### 3.6 容器与状态操作

| 名字 | 说明 |
|---|---|
| `add` | 构造函数里先绑成 `FlxG.state.add`，随后 `initPScript()` 调用的 `onAddSScript()` 会用 `setOnScripts("add", ...)` 把它**覆盖成与 HScript 相同的「智能插入」版**：`add(obj, ?front)`，`front = true` 加到最上层，否则插到 `dadGroup`/`boyfriendGroup`/`gfGroup` 之前 |
| `remove` | `FlxG.state.remove` |
| `insert` | `FlxG.state.insert(position, obj)` |
| `members` | `FlxG.state.members` 数组 |
| `foreground` | 本脚本的前景组（需自己 `game.add(foreground)`） |
| `pauseScript()` | 暂停自己 |
| `resumeScript()` | 恢复自己 |
| `setScriptPaused(tag, paused)` | 按脚本名/文件名暂停任意脚本 |

### 3.7 只在歌曲中注册的（`FlxG.state is PlayState && PlayState.instance != null`）

| 名字 | 说明 |
|---|---|
| `modManager` | `PlayState.modManager` 快照。**坑**：`modManager` 在 `PlayState.create()` 里晚于 `globals scripts/` 的加载，所以 `scripts/*.py` 拿到的可能是 `null`；`data/<song>/*.py` 在 `startSong()` 里加载，正常可用。另外引擎**从不**调用 `setDefaultPScripts()`，所以 `null` 不会被补上 |
| `global` | `PlayState.variables` 共享变量表 |
| `setGlobalFunc(name, func)` | 往共享表里放函数 |
| `callGlobalFunc(name, ?args)` | 调用共享表里的函数（多参数要打包成数组/结构传） |

### 3.8 `onAddSScript()` 注入的对局变量

脚本加载器（`initPScript()`）在建好脚本后立刻调用 `PlayState.onAddSScript()`，它会把这些值逐个 `set` 进 Python 环境（`setOnScripts()` → `setOnPScripts()`）。**共 20 个变量 + 1 个被覆盖的函数**：

| 变量 | 类型 | 更新时机 |
|---|---|---|
| `curStep` / `curBeat` | `Int` | **仅加载那一刻**（和 HScript 一样不会随歌曲更新，用回调参数或 `game.curStep`） |
| `curSection` | `Int` | 加载时 + 每次 `sectionHit()` |
| `bpm` | `Float` | 仅加载那一刻 |
| `camGame` / `camHUD` / `camOther` | `FlxCamera` | 加载时 |
| `camFollow` | `FlxPoint` | 加载时 |
| `camFollowPos` | `FlxObject` | 加载时 |
| `boyfriend` / `dad` / `gf` | `Boyfriend` / `Character` / `Character` | 加载时（换角色后可能过期，稳妥写法 `game.boyfriend`） |
| `boyfriendGroup` / `dadGroup` / `gfGroup` | `FlxSpriteGroup` | 加载时 |
| `notes` | `FlxTypedGroup<Note>` | 加载时 |
| `strumLineNotes` | `FlxTypedGroup<StrumNote>` | 加载时 |
| `playerStrums` / `opponentStrums` | `FlxTypedGroup<StrumNote>` | 加载时 |
| `unspawnNotes` | `Array<Note>` | 加载时（数组引用稳定） |
| `add` | 函数 | 被覆盖成智能插入版 `add(obj, ?front)`，见 §3.6 |

---

## 4. 回调支持度

Python 的回调派发与 HScript **完全同一条链**：

```
callOnScripts(event, args) → callOnHScripts(...) → callOnLScripts(...) → callOnPScripts(...) → FunkinPython.call(event, args) → PyScript.callFunc(event, args)
```

所以 **`hscript.md` §2.2 里那张表**（`onCreatePost`、`onLoad`、`onStartCountdown`、`preModifierRegister`、`postModifierRegister`、`generateModchart`、`onCountdownTick`、`onSongStart`、`onUpdate`、`onUpdatePost`、`onStepHit`、`onBeatHit`、`onSectionHit`、`onUpdateScore`、`onSpawnNote`、`goodNoteHit`、`opponentNoteHit`、`noteMiss`、`noteMissPress`、`popUpScore`、`SkinNoteSplash`、`onEvent`、`onMoveCamera`、`onPause`、`onResume`、`onGameOver`、`onRecalculateRating`、`onEndSong`、`eventEarlyTrigger`）**对 Python 一样成立，参数也完全一样**。

差异只有三点：

1. **`onCreate`**：不是 `callOnScripts` 派发的，而是 `FunkinPython.execute()` 在跑完顶层代码后直接 `call('onCreate')`。
2. **`onDestroy`**：由 `PlayState.destroy()` 里的 `py.call('onDestroy')` 直接调用。
3. **脚本状态（`states/<名字>.lua` / `.lscript` / `.hx`）不存在 Python 版本**：`FNFGame.switchState()` 不查 `.py`，`LuaSState` / `LScriptSState` / `OScriptState` 也只分别管自己的语言。

Lua 专属、Python 收不到的：`onKeyPress`、`onKeyRelease`、`onGhostTap`、`onCountdownStarted`、`onCustomSubstate*`、`onGameOverStart`、`onGameOverConfirm`、`onNextDialogue`、`onSkipDialogue`、`onUpdateOptions`、`onEventSet`。

**没定义的回调不会报错**：`PScript.callFunc()` 找不到函数时直接 `return "FUNC_CONT"`（即 `Function_Continue`），连警告都不打。所以回调写错名字是静默失效的——这是排查 Python 脚本时的头号坑。

### 参数怎么传

参数是**按位置**塞进函数形参的：

```python
def onStepHit(step):        # step ← callOnPScripts 的第 1 个参数（Int）
    pass

def onUpdate(elapsed):      # elapsed ← Float
    pass

def onEvent(name, v1, v2):  # 三个参数按顺序
    pass
```

形参名随便起；**形参比实参多 → 多出来的为 `None`；形参比实参少 → 多余的实参被丢弃**（不会报错）。

---

## 5. 返回值与暂停

- Python 函数返回什么，`callOnPScripts()` 就看到什么。没写 `return` → `null` → 引擎按 `Function_Continue` 处理。
- 三个常量已经注册好，所以可以：

  ```python
  def onPause():
      return Function_Stop      # 等价于 'FUNC_STOP'，可以阻止暂停菜单打开
  ```

- 语义与 HScript 完全一致（`PlayState.callOnHScripts` / `callOnPScripts` 是同一套逻辑）：**`ignoreStops` 默认是 `True`，所以 `Function_Stop` 一般不会中断其它脚本**，只会把整条链的聚合返回值变成 `'FUNC_STOP'`。真正会读它的调用点是 `openPauseMenu()` 的 `onPause`（以及 `doDeathCheck()` 的 `onGameOver`，但那里用的是 `||` 条件，单独一个 Stop 拦不住）。
- `eventEarlyTrigger` 的返回值会被 `cast` 成 Float 当作「提前毫秒数」——这个回调**不要返回字符串常量**。
- 暂停：`pauseScript()` / `resumeScript()` 作用于自己，`setScriptPaused(tag, paused)` 可以按名字控制别人。被暂停的脚本留在数组里、状态不丢，只是不再收回调。

---

## 6. 示例

### 6.1 最小可跑脚本

```python
# mods/<模组>/scripts/hello_python.py
# 顶层代码在加载时执行一次，然后才轮到 onCreate

greeting = "Hello from Python!"

def onCreate():
    # game 是 PlayState.instance；add(txt, True) / add(txt) 见上文「容器与状态操作」
    txt = FlxText(0, 0, 0, greeting, 24)
    txt.screenCenter()
    game.add(txt, True)

def onStepHit(step):
    if step % 8 == 0:
        game.camHUD.alpha = 0.85
    else:
        game.camHUD.alpha = 1.0

def onUpdate(elapsed):
    # elapsed 是每帧秒数
    if game.health < 0.2:
        game.camHUD.alpha = 0.9
    else:
        game.camHUD.alpha = 1.0

def onDestroy():
    return Function_Continue
```

### 6.2 用共享变量表跨回调存状态

解释器的 Python 语义是子集，跨回调保存状态最稳的做法是**在容器里原地改**，或直接用引擎的共享表 `global`：

```python
stats = {"hits": 0}

def goodNoteHit(note):
    stats["hits"] = stats["hits"] + 1
    if stats["hits"] % 50 == 0:
        print("50 combo!")

def noteMiss(daNote):
    stats["hits"] = 0
```

### 6.3 在 Python 里用未注册的引擎类

```python
FlxBar = Type.resolveClass("flixel.ui.FlxBar")
bar = Type.createInstance(FlxBar, [0, 0, None, 400, 20])
game.add(bar)
```

### 6.4 舞台 / 音符类型 / 事件脚本

```python
# mods/<模组>/stages/myStage.py           —— 加载舞台时执行
# mods/<模组>/custom_notetypes/myType.py  —— 谱面里出现该音符类型时执行
# mods/<模组>/custom_events/myEvent.py    —— 谱面里出现该事件时执行

def onEvent(name, value1, value2):
    if name == "My Event":
        game.camHUD.alpha = 0.5        # 颜色值请直接写整型，例如 0xFFFFFFFF
```

---

## 7. 限制与坑（都是源码事实）

1. **没有 `this`**。HScript 的默认 API 里有 `hscript.set('this', ...)`，`FunkinPython` 里完全没有对应项。父对象只能通过 `script.parent` 拿 —— 而它**在脚本体和 `onCreate` 里还是 `None`**，因为 `initPScript()` 的顺序是先 `execute()` 再 `setParent(this)`。之后的回调里 `script.parent` 才是 `PlayState`。
2. **父对象优先用 `game`**。`game` 在构造时就赋值好了（可能为 `None`，在有对局的加载路径下不会是）。
3. **`modManager` 可能是 `None`**：见 §3.7。`scripts/*.py` 的加载早于 `modManager` 创建；`setDefaultPScripts()` 引擎从不调用，所以不会像 HScript 那样被补写。
4. **没有 `FlxColor`**。`applyColorWorkarounds()` 会把 `FlxColor.fromRGB(r,g,b)` 改写成 `FlxColor().setRGB(r,g,b)`，但 `FlxColor` 从未注册，`PScript.registerHaxeClass()` 也没有被引擎调用（类注册表是空的）。**颜色直接写整型 `0xFFFFFFFF`**，或用 `Type.resolveClass("flixel.util.FlxColor")` 自己拿。
5. **`add()` 在「脚本体」和「回调」里不是同一个函数**：构造时绑的是 `FlxG.state.add`（歌曲里就是 `PlayState.add`，直接追加到末尾），`onAddSScript()` 跑完之后才换成与 HScript 相同的智能插入版 `add(obj, ?front)`。所以顶层代码里的 `add(spr)` 和 `onCreate` 之后的 `add(spr)` 落点可能不同；`insert` / `remove` / `members` 则一直是构造时的 `FlxG.state.*` 快照。
6. **`print` / 错误信息依赖 `LUA_ALLOWED`**：`PyScript.onError` 和 `onPrint` 都调用 `PlayState.instance.addTextToDebug(...)`，这个方法整体在 `#if LUA_ALLOWED` 里，而且**没有 null 检查**——在没有 PlayState 的时候（理论上会从 `states/` 之外的路径创建脚本）会二次崩溃。
7. **回调名写错 = 静默失效**，不会报错（`callFunc` 对不存在的函数返回 `FUNC_CONT`）。
8. **`scripts/*.py` 需要 `LUA_ALLOWED`**：`loadGlobalScripts()` 的整个函数体包在 `#if LUA_ALLOWED` 里。`data/<song>/*.py`、舞台、音符类型、事件脚本不受影响。
9. **`data/<song>/` 与 `scripts/` 的 `.py` 查找不递归子目录**（HScript 那两条路径是递归的，Python 不是）。
10. **Python 没有状态覆盖**：`states/globals/<Name>.hx` 那套机制没有 Python 版本。
11. **`stop()` 之后脚本变成空壳**：`PyScript.interpreter = null`，所有 `call` 都返回 `Function_Continue`。
12. **解释器是自研的 Python 子集**（`pyscript.core.Interpreter`），不是 CPython。装饰器、生成器、`with`、异常链这类进阶语法的支持情况需要逐条验证——**先在游戏里试跑，再写进你的模组**，不要照搬 CPython 的写法。
13. **`pyscript` 仓库自带的 `example/` 针对的是旧 API**：它 `import pyscript.Interpreter`，但当前 `pyscript/PyScript.hx` 里根本没有 `Interpreter` 类，也没有 `parent` 这个全局。那些示例（包括 `parent.add(spr)` 的写法）在本引擎里**不成立**，请用 `game.add(spr)` / `script.parent`。

---

## 8. 三种脚本语言对照

| | HScript | Python | Lua（Psych 方言） |
|---|---|---|---|
| 扩展名 | `.hx` / `.hscript` / `.hsc` / `.hxs` | `.py` | `.lua` |
| 默认全局 API | 72 个（+25 个对局注入） | 65 个（+20 个对局注入） | Psych 的 `_G` 大礼包（另见 Lua 文档） |
| `this` | 有（脚本创建时的 `FlxG.state`） | 无 | 通过 `setProxy()` 给 `this` 一个活的代理 |
| 状态覆盖 | 有（`states/globals/`，回调未接线） | 无 | 有（`states/<Name>.lua`，回调最全） |
| 角色脚本 | 有（`characters/<name>.hx`） | 无 | 无 |
| 暂停/恢复 | 有 | 有 | 有 |
| 错误显示 | 屏幕 + 原生弹窗 | 屏幕（`print`/错误都走 `addTextToDebug`） | 屏幕 |
