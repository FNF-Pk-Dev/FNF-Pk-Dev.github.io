<!-- source: modchart/ModManager.hx -->
<!-- source: modchart/Modifier.hx -->
<!-- source: modchart/NoteModifier.hx -->
<!-- source: modchart/SubModifier.hx -->
<!-- source: modchart/Modcharts.hx -->
<!-- source: modchart/EventTimeline.hx -->
<!-- source: modchart/HScriptModifier.hx -->
<!-- source: modchart/events/BaseEvent.hx -->
<!-- source: modchart/events/ModEvent.hx -->
<!-- source: modchart/events/SetEvent.hx -->
<!-- source: modchart/events/EaseEvent.hx -->
<!-- source: modchart/events/ModEaseEvent.hx -->
<!-- source: modchart/events/CallbackEvent.hx -->
<!-- source: modchart/events/StepCallbackEvent.hx -->
<!-- source: modchart/modifiers/*.hx -->
<!-- source: states/game/PlayState.hx -->
<!-- source: substates/game/GameplayChangersSubstate.hx -->
<!-- source: backend/ClientPrefs.hx -->

# Modchart（音符修饰器系统）

> **适用版本：Parker Engine 0.2.8**（`Project.xml` 的 `<app version>`）。参考工具链：Haxe 4.3.7 + HaxeFlixel。
>
> **本文以源码为准。** 修饰器注册名、参数（次模）、排序值、事件类型都是从 `source/modchart/` 逐个读出来的；源码里有、但当前版本实际跑不到的东西（例如 `Modifier.active`、`HScriptModifier` 这条路径）都在 §7 / §8 明确标注。

引擎里的 Modchart 是 **Schmovin' / Andromeda 风格的「修饰器栈」**，源码全在 `source/modchart/`。它和 `backend/Paths.hx` 那套「mod 文件夹」毫无关系——`ModManager` 是**修饰器（modifier）注册表**，不是模组管理器。也不同于维基里另一页记录的 Andromeda「ModChat / Modifiers」（note-field + `startMod()` 那套）：那是另一套系统，本页只讲 `source/modchart/`。

---

## 1. 概念

* **Modifier（修饰器）**：一个有名、有值（percent）、可带次模（submod）的变换单元。同一个修饰器对两侧玩家各存一个值（`percents = [0, 0]`），值 = 百分比 / 100——`setValue('drunk', 0.5)` 表示 50%。
* **玩家编号**：`player = 0` 是**玩家侧**（`playerStrums` / bf），`player = 1` 是**对手侧**（`opponentStrums` / dad）。传 `-1` 表示「两侧都设」。
* **两类修饰器**（`ModifierType`）：
  * `NOTE_MOD` —— 参与 note / receptor 的位置与渲染管线（`getPos` / `updateNote` / `updateReceptor`）。
  * `MISC_MOD` —— 其他一切，只作为 `Modifier` 基类默认值。
* **管线**（每帧，`PlayState.update()`）：

  ```
  modManager.updateTimeline(curDecStep)      // 跑 EventTimeline 上的计划事件（step 为单位）
  modManager.update(elapsed)                 // 见 §8 的注意：当前实际不会调用任何修饰器的 update()

  // 每根 strum（startedCountdown && songIsModcharted）
  pos = modManager.getPos(0, 0, 0, curDecBeat, strum.noteData, player, strum, [], strum.vec3Cache)
  modManager.updateObject(curDecBeat, strum, pos, player)   // 让 NOTE_MOD 改缩放/角度/alpha
  strum.x = pos.x; strum.y = pos.y

  // 每个 note（同上，getPos 用 strumTime + getVisPos 求视觉差）
  pos  = modManager.getPos(strumTime, visDiff, strumTime - songPosition, curBeat, noteData, player, note, [], note.vec3Cache)
  modManager.updateObject(curBeat, note, pos, player)
  note.x = pos.x; note.y = pos.y
  // sustain 尾巴：对「75ms 之后」的位置再算一次 getPos，用两点方向给 note.mAngle
  ```

* `getPos(time, diff, tDiff, beat, data, player, obj, ?exclusions, ?pos)` 的初始位置：

  ```haxe
  pos.x = getBaseX(data, player);   // strum 基准 x（含左右两侧偏移）
  pos.y = 50 + diff;                // diff = 视觉滚动差
  pos.z = 0;
  ```

  然后按 `activeMods[player]` 的顺序（已按 `getOrder()` 升序排好）依次调用 `mod.getPos(...)`；`exclusions` 里的名字会被跳过（`AlphaModifier` 就靠它重算一次「不含 reverse」的位置）。`getVisPos(songPos, strumTime, songSpeed)` = `-(0.45 * (songPos - strumTime) * songSpeed)`。

* **单位**：`EventTimeline` 用 **step**（`curDecStep`，可以是小数），不是 beat、不是秒。

---

## 2. 启用与注册时序

Modchart 不需要「手工开启」——引擎默认就开着，开关是一个 gameplay setting：

| 位置 | 内容 |
|---|---|
| `backend/ClientPrefs.hx` | `gameplaySettings` 默认值里有 `'modchart' => true` |
| `substates/game/GameplayChangersSubstate.hx` | `new GameplayOption('ModChart', 'modchart', 'bool', true)`（游戏内设置页开关） |
| `states/game/PlayState.hx:409` | `songIsModcharted = ClientPrefs.getGameplaySetting('modchart', true);` |
| `states/game/PlayState.hx:1046` | `modManager = new ModManager(this);`（在 `generateSong()` 之后） |
| `states/game/PlayState.hx:1048-1049` | `setDefaultLScripts("modManager", modManager)` / `setDefaultHScripts(...)` —— 让脚本拿到同一个实例 |
| `modchart/ModManager.hx:178` | `new ModManager(state)` 自己也会读同一个设置；为 `false` 时把内部 `state` 置空 |

`songIsModcharted == false` 时，`PlayState` 完全跳过 strum/note 的 `getPos` + `updateObject`（修饰器的值照样能设、事件照样跑，只是不会作用到画面上）。

注册时序（`PlayState.startCountdown()` → 完成时）：

```haxe
modManager.receptors = [playerStrums.members, opponentStrums.members];  // 注意 0 = 玩家侧
callOnLuas('preModifierRegister', []);
callOnScripts('preModifierRegister', []);      // HScript + LScript + Python
modManager.registerDefaultModifiers();         // ← 内置修饰器在这里注册
callOnLuas('postModifierRegister', []);
callOnScripts('postModifierRegister', []);
// Modcharts.loadModchart(modManager, SONG.song);   ← 源码里被注释掉了
```

也就是说：**`preModifierRegister` 里内置修饰器还不存在**（改它们的值要等到 `postModifierRegister`）；`registerDefaultModifiers()` 会把每个内置修饰器的值重置为 0。

### 相关回调

| 回调 | 时机 | 参数 | 备注 |
|---|---|---|---|
| `preModifierRegister` | 建好 strums 之后、注册内置修饰器之前（`PlayState:1881`，只到 HScript/LScript/Python） | 无 | `modManager.receptors` 已经可用 |
| `postModifierRegister` | 注册内置修饰器之后（`PlayState:1884`） | 无 | **设置初始 mod 值的标准位置** |
| `generateModchart` | 倒计时每个 tick，与 `onCountdownTick` 同处（`PlayState:2055`），共 5 次（swagCounter 0→4） | 无 | 写 `queueSet` / `queueEase` 谱面的标准位置；只到 HScript/LScript/Python（`callOnLuas` 那份是给 Lua 的） |

---

## 3. 内置修饰器全表（16 个注册名）

`registerDefaultModifiers()` 实际注册的名字如下（注册名 = `Modifier.getName()`，也就是 `setValue('名字', ...)` 里用的字串）：

| 注册名 | 类（文件） | 作用 |
|---|---|---|
| `flip` | `FlipModifier` | 左右镜像整条轨道 |
| `reverse` | `ReverseModifier` | 反向滚动 / 反转下落方向 |
| `invert` | `InvertModifier` | 交换相邻两列（0↔1、2↔3） |
| `drunk` | `DrunkModifier` | 喝醉式摇晃（x/y/z 全带） |
| `beat` | `BeatModifier` | 跟着节拍横向弹一下 |
| `stealth` | `AlphaModifier` | 隐身 / 透明度（hidden、sudden、blink…） |
| `mini` | `ScaleModifier` | 缩放、拉伸、挤压 |
| `confusion` | `ConfusionModifier` | 旋转 note / receptor |
| `opponentSwap` | `OpponentModifier` | 把一侧推到另一侧（0.5 = 中间滚动） |
| `transformX` | `TransformModifier` | 直接位移 x/y/z（像素） |
| `infinite` | `InfinitePathModifier`（继承 `PathModifier`） | 沿 3D 闭合圆环路径运动 |
| `perspectiveDONTUSE` | `PerspectiveModifier` | z → 透视投影，**别手动设值** |
| `rotateX` | `RotateModifier` | 绕各列自身原点旋转 |
| `centerrotateX` | `RotateModifier`（origin = 屏幕中心） | 绕屏幕中心旋转 |
| `localrotateX` | `LocalRotateModifier` | 绕固定局部原点旋转（preserve z 尺度） |
| `noteSpawnTime` | `SubModifier` | 纯数值槽，注册时默认 1250 |

说明：

* `PerspectiveModifier` 的 `getOrder()` 是 `LAST + 100`（= 1100），`RotateModifier` 是 `LAST + 2`（= 1002），`ScaleModifier` 是 `PRE_REVERSE`（= -3），`ReverseModifier` 是 `REVERSE`（= -2），`LocalRotateModifier` 是 `POST_REVERSE`（= -1），`TransformModifier` 是 `LAST`（= 1000），其余为 `DEFAULT`（= 0）。顺序决定 `getPos` 乘算的先后。
* 所有 `getSubmods()` 列出的次模 **也会以各自的名字被单独注册**（`registerMod` 里递归 `quickRegister`），所以 `setValue('hidden', 1, 0)` 这类写法合法；次模带 `parent`，设置次模的值会**连带把父修饰器激活**（`ModManager.setValue` 里靠 `mod.parent` 找父级）。
* `noteSpawnTime`：源码里除注册与 `setValue(..., 1250)` 之外没有任何地方读它，是留给脚本的数值槽。
* `Modcharts.hx` 目前是**死代码**：`isModcharted()`（只有 `["fresh"]` 在列表里）与 `loadModchart()` 都没有调用者，PlayState 里唯一那行是注释（`// Modcharts.loadModchart(modManager, SONG.song);`）。它原本要做的是：`ClientPrefs.middleScroll` 时给对手侧设 `opponentSwap = 0.5`、`alpha = 1`。

### 3.1 `flip`

| 项 | 内容 |
|---|---|
| 注册名 | `flip` |
| 类型 | `NoteModifier`（NOTE_MOD） |
| 作用 | `pos.x += Note.swagWidth * (receptors.length / 2) * (1.5 - data) * value`，即把整条轨道左右镜像；`value = 1` 时 0↔3、1↔2 完全对调 |
| 参数 | 无 |

### 3.2 `reverse`

| 项 | 内容 |
|---|---|
| 注册名 | `reverse` |
| 类型 | `NoteModifier`，`getOrder() = REVERSE (-2)` |
| 作用 | `value` 是「反向程度」：0 = 正常向上滚，1 = 完全反向下落。`pos.y = shift + visualDiff * mult`，`shift` 由 value 在 `50 … FlxG.height - 150` 之间插值，`mult` 在 `1 … -1` 之间插值；`ClientPrefs.downScroll` 打开时自动取反。sustain 长条还有一套专门的贴合/裁剪修正（`clipRect`） |

| 次模 | 说明 |
|---|---|
| `reverse` | 就是主值（`getValue`），整个轨道反向 |
| `reverse0` `reverse1` `reverse2` `reverse3` | 单列反向 |
| `split` | 右半边列（`dir >= kNum / 2`）反向 |
| `alternate` | 奇数列（`dir % 2 == 1`）反向 |
| `cross` | 中间若干列（`kNum/4 ≤ dir ≤ kNum-1-kNum/4`）反向 |
| `reverseScroll` / `crossScroll` / `splitScroll` / `alternateScroll` | 同上，但只改滚动方向（`getReverseValue(..., scrolling = true)` 的那一路），不参与位置计算 |
| `centered` | 把 `shift` 从 `50 … height-150` 改成 `height / 2 - 56`（以屏幕中心为轴反向） |
| `unboundedReverse` | 置 1 时不做 `val %= 2` 的折叠（允许反向超过一圈） |

### 3.3 `invert`

| 项 | 内容 |
|---|---|
| 注册名 | `invert` |
| 类型 | `NoteModifier` |
| 作用 | `pos.x += Note.swagWidth * ((data % 2 == 0) ? 1 : -1) * value`，交换相邻列 |
| 参数 | 无 |

### 3.4 `drunk`

| 项 | 内容 |
|---|---|
| 注册名 | `drunk` |
| 作用 | 以时间（`Conductor.songPosition / 1000`）为变量的余弦摇晃：`drunk` 走 x、`tipsy` 走 y、`tipZ` 走 z、`bumpy` 走 z（另一条公式） |

| 次模 | 说明 |
|---|---|
| `drunk` | 主值，x 轴摇摆幅度 |
| `drunkSpeed` / `drunkOffset` / `drunkPeriod` | x 摇摆的频率 / 列间相位 / 视觉差周期系数 |
| `tipsy` | y 轴摇摆幅度 |
| `tipsySpeed` / `tipsyOffset` | y 摇摆频率 / 列间相位 |
| `tipZ` | z 轴摇摆幅度 |
| `tipZSpeed` / `tipZOffset` | z 摇摆频率 / 列间相位 |
| `bumpy` | z 轴起伏幅度（按 `visualDiff` 而非时间） |
| `bumpyPeriod` / `bumpyOffset` | z 起伏的周期 / 相位 |
| `drunkZ` `drunkZSpeed` `drunkZOffset` `drunkZPeriod` | **只出现在 `getSubmods()` 里，`getPos` 没有读它们**（写了不会有任何效果） |

### 3.5 `beat`

| 项 | 内容 |
|---|---|
| 注册名 | `beat` |
| 作用 | 节拍同步的横向位移：取 `PlayState.curBeat + 0.3` 的小数部分，`< 0.3` 加速、到 `0.7` 结束（`accelTime = 0.3`、`totalTime = 0.7`），`shift = 40 * amount * sin(visualDiff / 30 + π/2)`；当 `(curBeat + 0.3) % 2 != 0` 时整体取负（源码变量名叫 `evenBeat`，条件写的却是 `!= 0`） |
| 参数 | 无 |

### 3.6 `stealth`

| 项 | 内容 |
|---|---|
| 注册名 | `stealth` |
| 类型 | `NoteModifier`，`ignorePos() = true`（不参与 `getPos`，只在 `updateNote` / `updateReceptor` 里改透明度） |
| 作用 | 主值 = 整体变暗（`alpha -= value`）；写的是 `note.colorSwap.daAlpha` 与 `receptor.colorSwap.daAlpha`（以及 glow） |
| 静态可调 | `AlphaModifier.fadeDistY = 120`（hidden/sudden 的渐隐距离） |

| 次模 | 说明 |
|---|---|
| `alpha` | 整体透明乘数（`1 - alpha`） |
| `noteAlpha` | 只对 note 的透明乘数 |
| `alpha0`…`alpha3` / `noteAlpha0`…`noteAlpha3` | 单列的上去两参数 |
| `hidden` | 上半屏渐隐 |
| `hiddenOffset` | hidden 分界的上下偏移 |
| `sudden` | 下半屏渐显 |
| `suddenOffset` | sudden 分界的上下偏移 |
| `blink` | 闪烁（用 `FlxMath.fastSin(time * 10)` 量化） |
| `randomVanish` | 按位置随机消失 |
| `dark` / `dark0`…`dark3` | receptor 变暗 |
| `stealthPastReceptors` | 置 1 时「已越过 receptor 的 note」也参与隐身计算 |
| `useStealthGlow` | **实际无效**：`getSubmods()` 注册的是 `useStealthGlow`，但 `updateNote()` 读的是 `dontUseStealthGlow`；未知名字一律返回 0，条件恒成立，所以永远走 glow 分支 |

### 3.7 `mini`

| 项 | 内容 |
|---|---|
| 注册名 | `mini` |
| 类型 | `NoteModifier`，`getOrder() = PRE_REVERSE (-3)`，`ignorePos() = true` |
| 作用 | 主值 = 整体缩小（`scale *= 1 - value`，1 就是完全看不见）；sustain 长条的 y 缩放会被还原，避免长度变形 |

| 次模 | 说明 |
|---|---|
| `miniX` / `miniY` | 单独的 x / y 缩小 |
| `mini0X`…`mini3X` / `mini0Y`…`mini3Y` | 单列缩小 |
| `stretch` / `stretch0`…`stretch3` | 拉伸（x→0.5、y→2 插值） |
| `squish` / `squish0`…`squish3` | 挤压（x→2、y→0.5 插值） |

（`getScale()` 里 `var angle = 0;` 是硬编码的，所以旋转相关的两项其实恒等于 1×……它只影响 stretch/squish 的组合系数。）

### 3.8 `confusion`

| 项 | 内容 |
|---|---|
| 注册名 | `confusion` |
| 作用 | 旋转：`note.angle = value + confusion{N} + note{N}Angle`、`receptor.angle = value + confusion{N} + receptor{N}Angle`。sustain note 改用 `note.mAngle`（由 PlayState 根据两点方向算出的角度）。**单位是度**（直接写进 `FlxSprite.angle`） |

| 次模 | 说明 |
|---|---|
| `noteAngle` / `receptorAngle` | 全体 note / receptor 的额外角度 |
| `note0Angle`…`note3Angle` / `receptor0Angle`…`receptor3Angle` | 单列角度 |
| `confusion0`…`confusion3` | 单列的主值增量 |

### 3.9 `opponentSwap`

| 项 | 内容 |
|---|---|
| 注册名 | `opponentSwap` |
| 作用 | 把 note 从自己这侧推向对侧：`distX = getBaseX(data, 1-player) - getBaseX(data, player)`，`pos.x += distX * value`。`0.5` = 中间滚动（引擎在 `ClientPrefs.middleScroll` 时就是设 0.5） |
| 参数 | 无 |

### 3.10 `transformX`

| 项 | 内容 |
|---|---|
| 注册名 | `transformX` |
| 类型 | `NoteModifier`，`getOrder() = LAST (1000)` |
| 作用 | 直接往 `pos` 上加像素：`pos.x += value + transformX-a`，`pos.y += transformY + transformY-a`，`pos.z += transformZ + transformZ-a`，再加单列版 |

| 次模 | 说明 |
|---|---|
| `transformY` / `transformZ` | 主值的 y / z 分量（x 分量就是主值本身） |
| `transformX-a` / `transformY-a` / `transformZ-a` | 「附加」分量，跟在主值后面相加 |
| `transform0X`…`transform3X`、`transform0Y`…、`transform0Z`… | 单列位移 |
| `transform0X-a`…`transform3X-a`、`…Y-a`、`…Z-a` | 单列的附加分量 |

（`ClientPrefs.middleScroll` 时 PlayState 给对手侧设的就是 `transform0X`…`transform3X`。）

### 3.11 `infinite`

| 项 | 内容 |
|---|---|
| 注册名 | `infinite`（类名 `InfinitePathModifier`，继承 `PathModifier`） |
| 作用 | note 沿一条 3D 闭合曲线运动：半径 600 的圆，角度从 0° 到 345° 每隔 15° 取一点，四条轨道各自独立；`getMoveSpeed() = 1850` 决定「多快跑完一圈」。主值 = 沿路径插值的比例（0 = 原始位置，1 = 完全贴合路径） |
| 参数 | 无（`getSubmods()` 返回 `[]`） |

`PathModifier` 基类的注册名是 `basePath`（`getMoveSpeed() = 5000`、`getPath()` 返回空），**没有被注册**；路径在构造时预计算成 `PathInfo{position, start, end, dist}` 数组，并整体偏移 `-Note.swagWidth / 2`。

### 3.12 `perspectiveDONTUSE`

| 项 | 内容 |
|---|---|
| 注册名 | `perspectiveDONTUSE`（名字自带警告） |
| 类型 | `NoteModifier`，`getOrder() = LAST + 100 (1100)`，`shouldExecute()` 恒为 `true` |
| 作用 | 把 `pos.z` 做透视投影回 x/y（`fov = π/2`、`near = 0`、`far = 2`，aspect 硬编码为 1），并让 `updateReceptor` / `updateNote` 按 `1 / pos.z` 缩放精灵。它是给 `tipZ` / `bumpy` 这类 z 轴修饰器兜底的，**不要手动设值** |
| 参数 | 无 |

### 3.13 `rotateX`

| 项 | 内容 |
|---|---|
| 注册名 | `rotateX` |
| 类型 | `NoteModifier`，`getOrder() = LAST + 2 (1002)` |
| 作用 | 绕「该列自己的原点」旋转：原点 = `(modMgr.getBaseX(data, player), FlxG.height / 2 - Note.swagWidth / 2)`。计算时 `diff.z` 先乘 `FlxG.height`，旋转完再除回来 |
| 参数 | `rotateY`、`rotateZ`（次模，分别绕 Y / Z 轴） |

**角度单位是弧度**：内部用 `CoolUtil.rotate(x, y, angle)`，而它是 `Math.cos(angle)` / `Math.sin(angle)`。

### 3.14 `centerrotateX`

| 项 | 内容 |
|---|---|
| 注册名 | `centerrotateX` |
| 类型 | 同 `RotateModifier`，但构造时把原点固定成 `(FlxG.width / 2 - Note.swagWidth / 2, FlxG.height / 2 - Note.swagWidth / 2)` |
| 作用 | 绕屏幕中心整片旋转 |
| 参数 | `centerrotateY`、`centerrotateZ` |

### 3.15 `localrotateX`

| 项 | 内容 |
|---|---|
| 注册名 | `localrotateX` |
| 类型 | `NoteModifier`（`LocalRotateModifier`），`getOrder() = POST_REVERSE (-1)` |
| 作用 | 原点 x 按 `swagWidth` 计算**且不含左右两侧偏移**（也就是「轨道局部坐标」的原点），旋转同样带 z 尺度换算 |
| 参数 | `localrotateY`、`localrotateZ` |

### 3.16 `noteSpawnTime`

| 项 | 内容 |
|---|---|
| 注册名 | `noteSpawnTime`（`new SubModifier("noteSpawnTime", this)`） |
| 作用 | 纯数值槽，注册后立刻 `setValue("noteSpawnTime", 1250)`。引擎源码里没有任何地方读它 |
| 参数 | 无 |

---

## 4. 数值与次模 API

| 方法 | 说明 |
|---|---|
| `setValue(modName, val, player = -1)` | 设值（`val` 是 0…1 的比例）。`player = -1` 递归设两侧；内部会按 `mod.parent` 找父修饰器、维护 `activeMods` 并按 `getOrder()` 重新排序 |
| `setPercent(modName, val, player = -1)` | 同上，参数是百分数（内部 `/ 100`） |
| `getValue(modName, player)` / `getPercent(modName, player)` | 读值（注意：源码里是 `inline`） |
| `get(modName)` | 取修饰器实例（`inline`） |
| `registerMod(modName, mod, ?registerSubmods = true)` | 注册（会连带注册所有次模、把值归零、重排 `modArray`） |
| `quickRegister(mod)` | 用 `mod.getName()` 注册 |
| `receptors` | `[playerStrums.members, opponentStrums.members]`，索引 **0 = 玩家侧** |

次模在脚本里的用法举例：`setValue('hidden', 1, 0)`（玩家侧上半渐隐）、`setValue('cross', 1)`（中间两列反向）、`setValue('transform0X', -100, 1)`。

---

## 5. 事件系统（EventTimeline）

`ModManager.timeline` 是一个 `EventTimeline`，由 `updateTimeline(curDecStep)` 每帧驱动。事件按 `executionStep` 排序，`step >= executionStep` 时 `run(step)`；跑完（`finished`）就移出队列。

| 事件类 | 说明 |
|---|---|
| `BaseEvent` | 基类：`manager`、`parent`、`executionStep`、`ignoreExecution`、`finished`、`run(curStep)` |
| `ModEvent` | 绑定一个 mod：`modName`、`endVal`、`player`，构造时就 `modMgr.get(modName)` 找实例 |
| `SetEvent` | 到 step 立刻把值设成 `endVal`，然后 `finished` |
| `EaseEvent` | 在 `step → endStep` 之间用 `EaseFunction` 把值从 `startVal`（不给就用当前值）缓动到 `endVal`；超过 `endStep` 后落地并 `finished` |
| `ModEaseEvent` | 与 `EaseEvent` 几乎相同，多一个「mod 名为空则报错退出」的保护，结束时设的是 `easeFunc(1) * endVal` |
| `CallbackEvent` | 一次性：到 step 调 `callback(this, curStep)` 后 `finished` |
| `StepCallbackEvent` | 从 `step` 到 `endStep` **每 step** 调一次 `callback`，并给出 `progress = (curStep - executionStep) / (endStep - executionStep)`（结束置 1） |

`ModManager` 上暴露的排队 API（脚本通过代理表调用的就是这些）：

| 方法 | 参数 |
|---|---|
| `queueSet(step, modName, target, player = -1)` | step 到点设值（`target` 是 0…1 比例） |
| `queueSetP(step, modName, percent, player = -1)` | 同上，百分数 |
| `queueEase(step, endStep, modName, target, style = 'linear', player = -1, ?startVal)` | 缓动（`target` / `startVal` 都是 0…1） |
| `queueEaseP(step, endStep, modName, percent, style = 'linear', player = -1, ?startVal)` | 同上，百分数（内部把两个值都 `/ 100`） |
| `queueFunc(step, endStep, callback)` | 区间内每 step 回调（`StepCallbackEvent`） |
| `queueFuncOnce(step, callback)` | 到点回调一次（`CallbackEvent`） |
| `randomFloat(minVal, maxVal)` | `FlxG.random.float` |

`style` 是 `FlxEase` 上的字段名（`Reflect.getProperty(FlxEase, style)`），例如 `'linear'`、`'quadInOut'`、`'cubeOut'`、`'sineIn'`……找不到就退回 `linear`。`step` / `endStep` 都可以是小数。

---

## 6. 从脚本操控

### LScript / HScript

引擎把 `modManager` 直接塞成脚本全局（`PlayState:1048` 的 `setDefaultLScripts` / `setDefaultHScripts`），所以：

```lua
function postModifierRegister()
	modManager:setValue('opponentSwap', 0.5)          -- 两侧
	modManager:setValue('mini', 0.25, 1)              -- 只对手侧
end

function generateModchart()
	modManager:queueEase(0, 16, 'drunk', 0.5, 'quadOut', 0)
	modManager:queueSet(32, 'reverse', 1)
	modManager:queueFuncOnce(48, function(event, step)
		modManager:setValue('flip', 0)
	end)
end
```

`ModManager` 的 `getValue` / `getPercent` / `get` / `getVisPos` / `quickRegister` / `setPercent` 都是 `inline`，经代理表 `Reflect.getProperty()` 反射未必取得到实体；稳妥做法是只用上表里那些非 inline 方法，要记数就自己维护变量。

### Lua

Lua 侧不需要碰 `modManager`，`FunkinLua` 直接注册了一整套同名函数：

| Lua 函数 | 等价于 |
|---|---|
| `setValue(modName, val, player = -1)` | `modManager.setValue` |
| `setPercent(modName, val, player = -1)` | `modManager.setPercent` |
| `getValue(modName, player)` / `getPercent(modName, player)` | 读值 |
| `queueSet(step, modName, target, player = -1)` | `modManager.queueSet` |
| `queueSetP(step, modName, perc, player = -1)` | `modManager.queueSetP` |
| `queueEase(step, endStep, modName, percent, style = 'linear', player = -1, ?startVal)` | `modManager.queueEase` |
| `queueEaseP(...)` | `modManager.queueEaseP` |
| `addBlankMod(modName, defaultVal = 0, player = -1)` | `quickRegister(new SubModifier(modName, modManager))` + `setValue`，即「注册一个纯数值槽」 |

---

## 7. 自定义修饰器

### 7.1 HScriptModifier（`source/modchart/HScriptModifier.hx`）

设计意图：用 HScript 写一个 `Modifier`，让引擎在 `getPos` / `updateNote` / `updateReceptor` 时回调脚本函数。

* `HScriptModifier.fromString(modMgr, ?parent, scriptSource)` —— 从字符串建；
* `HScriptModifier.fromName(modMgr, ?parent, scriptName)` —— 从 `modifiers/<scriptName>.hscript` 建（先 `Paths.modFolders()`，再 `Paths.getPreloadPath()`），并把 `mod.name` 设成脚本名；找不到就 `trace` 一条并返回 `null`。
* 脚本环境：构造时先把 `onAddScript` 钩子挂上，然后 `modchart()` 往脚本里塞 `this`（修饰器本身）、`modMgr`、`parent`，以及 `getValue` / `getPercent` / `getSubmodValue` / `getSubmodPercent` / `setValue` / `setPercent` / `setSubmodValue` / `setSubmodPercent`，最后依次执行 `onCreate`、`onCreatePost`。
* 转发给脚本的成员（`script.exitsVar(...)` 存在才转，否则用基类实现）：`getModType`、`ignorePos`、`ignoreUpdateReceptor`、`ignoreUpdateNote`、`doesUpdate`、`shouldExecute(player, value)`、`getOrder`、`getName`、`getValue(player)`、`getPercent(player)`、`setValue(value, player)`、`setPercent(percent, player)`、`getSubmods`、`getSubmodPercent`、`getSubmodValue`、`updateReceptor(beat, receptor, player)`、`updateNote(beat, note, player)`。
* `_scriptEnums`（`NOTE_MOD` / `MISC_MOD` / `FIRST` / `PRE_REVERSE` / `REVERSE` / `POST_REVERSE` / `DEFAULT` / `LAST`）本来是为 `FunkinHScript.fromString(..., enums)` 准备的，那两行现在是注释，枚举并没有被真正注入。

**完整示例**（按上面转发的方法名写）：

```haxe
// 路径：mods/<mod>/modifiers/wave.hscript
// 注册：Haxe 侧调用 HScriptModifier.fromName(modManager, null, 'wave')
//       —— 引擎没有任何目录扫描逻辑会自动加载它

var amplitude:Float = 40;   // 自定义次模，先写进 getSubmods() 才能被 setValue 驱动

function getName() return 'wave';
function getModType() return NOTE_MOD;                       // 参与 note / receptor 渲染
function getOrder() return DEFAULT;
function shouldExecute(player:Int, value:Float) return true; // 值归 0 时也想继续跑就返回 true
function getSubmods() return ['amplitude'];

function updateNote(beat:Float, note:Note, player:Int)
{
	wave(note, player);
}

function updateReceptor(beat:Float, receptor:StrumNote, player:Int)
{
	wave(receptor, player);
}

function wave(obj:FlxSprite, player:Int)
{
	var amount:Float = getValue(player);
	if (amount == 0) return;

	var amp:Float = getSubmodValue('amplitude', player);
	if (amp == 0) amp = amplitude;

	obj.y += Math.sin(Conductor.songPosition / 1000 * 4) * amp * amount;
}
```

**源码现状（必须知道）**：`HScriptModifier` 在当前树里**没有任何已编译代码引用它**（`HScriptUtil.hx:196` 那行是注释），而它自身对着本 fork 的 `Modifier` 有几处不一致，所以这条路径目前是**不可用/未维护**的：

1. 大量分支用 `script.exitsVar(...)`，但 `FunkinHScript` 上只有 `exists()`（`exitsVar` 全仓库只出现在这个文件里）；
2. `getPos` 的转发被**整段注释掉**了（`// override public function getPos(...)`）——也就是说 HScript 修饰器**无法参与位置计算**，只能在 `updateNote` / `updateReceptor` 里直接改精灵；
3. `updateNote(beat, note, player)` / `updateReceptor(beat, receptor, player)` 的形参个数与基类 `Modifier` 的 `(beat, note, pos, player)` / `(beat, receptor, pos, player)` 不一致；`update(elapsed, beat)` 也和 `Modifier.update(elapsed)` 不一致；
4. `getExtraInfo()` / `isRenderMod()` 依赖的 `RenderInfo`、`Modifier.getExtraInfo`、`Modifier.isRenderMod` 在本 fork 里根本不存在；
5. `setPercent` 内部转发的是 `executeFunc("setValue", ...)`（疑似笔误）。

因此**想加自定义修饰器，当前唯一可靠的做法是加一个 Haxe 类**：

```haxe
// source/modchart/modifiers/WaveModifier.hx
package modchart.modifiers;

import flixel.FlxSprite;
import math.Vector3;

class WaveModifier extends NoteModifier
{
	override function getName()
		return 'wave';                       // 注册名 / setValue 用的字串

	override function getOrder()
		return Modifier.ModifierOrder.DEFAULT;

	override function getSubmods()
		return ['amplitude'];

	override function getPos(time:Float, visualDiff:Float, timeDiff:Float, beat:Float, pos:Vector3, data:Int, player:Int, obj:FlxSprite)
	{
		var amp:Float = getSubmodValue('amplitude', player);
		if (amp == 0)
			amp = 40;

		pos.y += Math.sin(Conductor.songPosition / 1000 * 4) * amp * getValue(player);
		return pos;
	}
}
```

然后在 `ModManager.registerDefaultModifiers()` 的 `quickRegs` 数组里加 `WaveModifier`（或另找时机 `quickRegister(new WaveModifier(this))`），重新编译即可。`getPos` 里拿到的是待修改的 `Vector3`，`updateNote` / `updateReceptor` 里拿到的是精灵本身。

### 7.2 「纯数值槽 + 事件」的伪修饰器

如果只是想要一个被谱面驱动的数值（不做位置计算），可以模仿 `noteSpawnTime`：注册一个 `SubModifier`，用 `queueFunc` / `queueEase` 驱动它，再在自己的脚本回调里读取。Lua 端有现成的 `addBlankMod(modName, defaultVal, player)`；LScript 端可以 `import('modchart.SubModifier')` 后用 `modManager:registerMod('myValue', SubModifier:new('myValue', modManager))` 做同样的事（`SubModifier` 的构造签名是 `(name, modMgr, ?parent)`，默认 `getOrder()` 是 `LAST`、`doesUpdate()` 是 `false`）。

---

## 8. 已知限制与坑

1. **`Modifier.active` 永远是 `false`**。`ModManager.update(elapsed)` 的条件是 `if (mod.active && mod.doesUpdate()) mod.update(elapsed)`，而整个 `source/modchart/` 里没有任何地方把 `active` 设成 `true`。结论：**修饰器的 `update()` 钩子当前不可达**，每帧逻辑请写在 `queueFunc`（`StepCallbackEvent`）里。另外 `ignorePos()` / `ignoreUpdateNote()` / `ignoreUpdateReceptor()` 这三个开关**在整个仓库里都没有被调用过**（只有定义和 override），`updateObject()` 只检查 `obj.active`（FlxObject 的 active，正常恒为 true）——它们目前只是文档性/预留的成员。
2. **修饰器的值默认是 0，且不影响 `activeMods`**：`setValue` 里靠 `shouldExecute(player, val)`（默认 `val != 0`）决定是否进 `activeMods`；`AlphaModifier` / `ReverseModifier` / `ConfusionModifier` / `ScaleModifier` / `PerspectiveModifier` 覆写成恒 `true`，所以它们只要被设过值就一直留在 `activeMods` 里。
3. **次模会连带激活父修饰器**，所以「只设某一个次模」是正常用法（`setValue('hidden', 1, 0)`）。
4. **`preModifierRegister` 时内置修饰器还没注册**，设值会被 `registerDefaultModifiers()` 里的 `setValue(modName, 0)` 覆盖掉；请用 `postModifierRegister` 或 `generateModchart`。
5. **`songIsModcharted == false` 时画面不会变**，即使脚本照常设值、事件照常跑。
6. **`getPos` 的 `exclusions` 数组**是按修饰器注册名过滤的（例如 `AlphaModifier` 传入 `["reverse"]` 重算位置）；脚本自己调用 `getPos` 时也要自己传。
7. **`rotate*` 用弧度、`confusion` 用度**（前者经过 `CoolUtil.rotate` → `Math.cos/sin`，后者直接写 `FlxSprite.angle`）。
8. **`perspectiveDONTUSE` 不要手动设值**：它 `shouldExecute()` 恒 `true`，被激活后会把 z 按 `near = 0`、`far = 2`、`fov = π/2`、aspect 硬编码 1 投影，是给 z 轴修饰器兜底用的。
9. **`basePath` 未注册**：`PathModifier` 基类只有子类 `InfinitePathModifier`（注册名 `infinite`）被 `registerDefaultModifiers()` 注册。
10. **`stealth` 的 `useStealthGlow` 无效**（代码读的是 `dontUseStealthGlow`，见 §3.6）。
11. **`drunk` 的 `drunkZ` / `drunkZSpeed` / `drunkZOffset` / `drunkZPeriod` 无效**（只在 `getSubmods()` 里声明，`getPos` 未使用）。
12. **`mini` 里的 `angle` 恒为 0**，`stretch` / `squish` 的旋转耦合项实际是固定系数。
13. **`Modcharts.hx` 是死代码**（`isModcharted()`、`loadModchart()` 都没有调用者）。
