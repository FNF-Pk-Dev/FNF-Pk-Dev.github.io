# Psych 原版 Lua 函数全集

<!-- source: psych/script/FunkinLua.hx -->

本页收录 Parker Engine 中 `psych/script/FunkinLua.hx`（Psych 原版 Lua 运行时）**实际用 `set(...)` 注册过的全部 Lua 全局函数**，共 **234 个**（含 13 个已弃用函数）。

- 所有函数都注册在该脚本自己的 Lua 全局表里，脚本里直接按名字调用即可（例如 `makeLuaSprite('bg', 'stage/bg', 0, 0)`）。
- 参数签名照抄源码，`?name:Type = default` 表示可选参数及默认值；Lua 侧不写类型，类型只是引擎侧声明。
- 返回值一栏写的是「源码里真正 return 的东西」；源码没有 `return` 的函数就写「无返回」——即使它在别的 Psych 版本里有返回值。
- `Function_Stop` / `Function_StopLua` / `Function_Continue` 是三个内置常量：回调里 `return Function_Stop` 会中断后续脚本的同名回调分发，`return Function_StopLua`（值 `##PSYCHLUA_FUNCTIONSTOPLUA`）只中断 Lua 脚本链。
- 不在本页出现的函数，就是 Parker Engine 源码里**确实没有**的，不要凭 Psych 其他版本的记忆去调用。
- 引擎相对 Psych 的增量（`ESCompat` 注册的「Engine Custom ES」方言）另见 `lua-es-extensions.md`；Lua 的 `this` 全局见 `lua-this-proxy.md`。

---

## 通用函数

<!-- source: psych/script/FunkinLua.hx -->

本类包含脚本管理、音频、存档与文件、字符串、随机数、输入查询等通用工具。**本类共 71 个函数。**

### getRunningScripts()

返回当前正在运行的全部 Lua 脚本文件名（完整路径）。

参数：无。

返回：`Array<String>`，脚本的 `scriptName` 列表。

```lua
for i, name in ipairs(getRunningScripts()) do
	debugPrint(name)
end
```

### pauseScript()

暂停当前正在执行的这个 Lua 脚本（回调不再分发，`onUpdate` 不再运行）。

参数：无。

返回：`Bool`，暂停后的状态（恒为 `true`）。

### resumeScript()

恢复当前这个 Lua 脚本。

参数：无。

返回：`Bool`，恢复后的状态（恒为 `false`）。

### setScriptPaused(tag:String, paused:Bool)

按脚本名暂停/恢复任意一个脚本。菜单态脚本之间只能互相查找，没有 `PlayState` 时也走同一套菜单脚本列表。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 目标脚本名：完整 `scriptName`，或文件名（不含路径与扩展名的匹配由 `GlobalScript.scriptMatchesTag()` 处理） |
| `paused` | `Bool` | `true` 暂停，`false` 恢复 |

返回：`Bool`，是否找到并成功设置。

### callOnLuas(?funcName:String, ?args:Array<Dynamic>, ignoreStops = false, ignoreSelf = true, ?exclusions:Array<String>)

主动向全部 Lua 脚本广播一个回调。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `funcName` | `String` | 回调名，为 `nil` 时报 Lua 参数错误 |
| `args` | `Array` | 传给回调的参数，默认为空表 |
| `ignoreStops` | `Bool` | 收到 `Function_StopLua` 时是否继续分发，默认 `false` |
| `ignoreSelf` | `Bool` | 是否把自己的脚本名加进排除表（即不回调自己），默认 `true` |
| `exclusions` | `Array<String>` | 额外排除的脚本名列表 |

返回：无返回。菜单态下只回调自身，不广播。

### callScript(?luaFile:String, ?funcName:String, ?args:Array<Dynamic>)

调用另一个已运行的 Lua 脚本里的某个函数。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `luaFile` | `String` | 目标脚本路径（可省略 `.lua`）；会在 mod 目录、当前目录、preload 依次查找 |
| `funcName` | `String` | 要调用的函数名 |
| `args` | `Array` | 参数表，默认为空表 |

返回：无返回。

### getGlobalFromScript(?luaFile:String, ?global:String)

读取另一个脚本的全局变量。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `luaFile` | `String` | 目标脚本路径 |
| `global` | `String` | 全局变量名 |

返回：数值 / 字符串 / 布尔之一；类型不属于这三者时返回 `nil`（源码注释里明确写了 table 尚未支持）。

### setGlobalFromScript(luaFile:String, global:String, val:Dynamic)

写入另一个脚本的全局变量。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `luaFile` | `String` | 目标脚本路径 |
| `global` | `String` | 全局变量名 |
| `val` | `Dynamic` | 要写入的值 |

返回：无返回。

### isRunning(luaFile:String)

判断某个 Lua 脚本是否正在运行。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `luaFile` | `String` | 脚本路径，可省略 `.lua` |

返回：`Bool`。

### addLuaScript(luaFile:String, ?ignoreAlreadyRunning:Bool = false)

运行时加载并运行一个新的 Lua 脚本。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `luaFile` | `String` | 脚本路径，可省略 `.lua` |
| `ignoreAlreadyRunning` | `Bool` | `false`（默认）时若同一脚本已在运行则拒绝并打印提示；`true` 时跳过重复检查 |

返回：无返回。脚本文件不存在时红字提示。

### removeLuaScript(luaFile:String, ?ignoreAlreadyRunning:Bool = false)

停止并移除一个正在运行的 Lua 脚本。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `luaFile` | `String` | 脚本路径，可省略 `.lua` |
| `ignoreAlreadyRunning` | `Bool` | 传入 `true` 时跳过查找逻辑（几乎不用） |

返回：无返回。

### precacheImage(name:String, ?library:String, ?allowGPU:Bool = true)

预加载一张图片，避免用到时才卡顿。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 图片路径（相对 `images/`，不带扩展名） |
| `library` | `String` | 资源库名（`shared` / `week2`…），默认当前库 |
| `allowGPU` | `Bool` | 是否允许走 GPU 纹理路径，默认 `true` |

返回：无返回。

### precacheSound(name:String)

预加载一个音效。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 音效名（相对 `sounds/`） |

返回：无返回。

### precacheMusic(name:String)

预加载一首音乐（相对 `music/`）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 音乐名 |

返回：无返回。

### setVar(varName:String, value:Dynamic)

把值写进脚本变量表（全局共享的 `variables`）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `varName` | `String` | 变量名 |
| `value` | `Dynamic` | 值 |

返回：传入的 `value` 本身。

### getVar(varName:String)

读脚本变量表里的值。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `varName` | `String` | 变量名 |

返回：变量值；不存在时返回 `nil`。

### luaSoundExists(tag:String)

判断某个 tag 的 Lua 音效是否存在。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | `playSound` 时传入的 tag |

返回：`Bool`。

### playMusic(sound:String, volume:Float = 1, loop:Bool = false)

播放音乐（会替换当前音乐轨）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `sound` | `String` | 音乐名（相对 `music/`） |
| `volume` | `Float` | 音量，默认 `1` |
| `loop` | `Bool` | 是否循环，默认 `false` |

返回：无返回。

### playSound(sound:String, volume:Float = 1, ?tag:String = null)

播放音效。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `sound` | `String` | 音效名（相对 `sounds/`） |
| `volume` | `Float` | 音量，默认 `1` |
| `tag` | `String` | 可选 tag；给了 tag 才能用 `stopSound` / `pauseSound` / `soundFadeOut` 等控制，播完会回调 `onSoundFinished(tag)` |

返回：无返回。

### stopSound(tag:String)

停止并移除某个 tag 的音效。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 音效 tag |

返回：无返回。

### pauseSound(tag:String)

暂停某个 tag 的音效。

参数同上。

返回：无返回。

### resumeSound(tag:String)

继续播放某个 tag 的音效。

参数同上。

返回：无返回。

### soundFadeIn(tag:String, duration:Float, fromValue:Float = 0, toValue:Float = 1)

音量淡入。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 音效 tag；传空字符串或 `nil` 时作用于当前音乐（`FlxG.sound.music`） |
| `duration` | `Float` | 淡入时长（秒） |
| `fromValue` | `Float` | 起始音量，默认 `0` |
| `toValue` | `Float` | 目标音量，默认 `1` |

返回：无返回。

### soundFadeOut(tag:String, duration:Float, toValue:Float = 0)

音量淡出。参数含义同 `soundFadeIn`（`tag` 为空时作用于当前音乐）。

返回：无返回。

### soundFadeCancel(tag:String)

取消正在进行的淡入/淡出。`tag` 为空时取消当前音乐的淡变。

返回：无返回。

### getSoundVolume(tag:String)

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 音效 tag；空则读取当前音乐音量 |

返回：`Float` 音量；tag 音乐都不存在时返回 `0`。

### setSoundVolume(tag:String, value:Float)

设置音量，`tag` 为空时作用于当前音乐。

返回：无返回。

### getSoundTime(tag:String)

读取音效当前播放位置（毫秒）。

返回：`Float`；tag 不存在时返回 `0`。

### setSoundTime(tag:String, value:Float)

设置音效播放位置。内部会先 `pause`、改时间、若原本在播放再 `play`，避免爆音。

返回：无返回。

### debugPrint(text1:Dynamic = '', text2:Dynamic = '', text3:Dynamic = '', text4:Dynamic = '', text5:Dynamic = '')

在屏幕上打印调试文字（需要该脚本的 `luaDebugMode` 为 `true`）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `text1`…`text5` | `Dynamic` | 最多 5 段文本，依次拼接输出；`nil` 会被当成空串 |

返回：无返回。

### close()

标记此脚本已关闭。当前回调返回后脚本会被停止（`call()` 末尾检测到 `closed` 就 `stop()`）。

参数：无。

返回：`Bool`，恒为 `true`。

### changePresence(details:String, state:Null<String>, ?smallImageKey:String, ?hasStartTimestamp:Bool, ?endTimestamp:Float)

更新 Discord Rich Presence（仅桌面构建生效）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `details` | `String` | 第一行文字 |
| `state` | `String` | 第二行文字，可为 `nil` |
| `smallImageKey` | `String` | 小图标 key |
| `hasStartTimestamp` | `Bool` | 是否显示计时 |
| `endTimestamp` | `Float` | 计时终点（秒） |

返回：无返回。

### vibration(milliseconds:Int)

让设备振动（仅 Android 生效）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `milliseconds` | `Int` | 振动毫秒数 |

返回：无返回。

### initSaveData(name:String, ?folder:String = 'psychenginemods')

初始化一个存档文件（FlxSave）。重复初始化会打印提示。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 存档名 |
| `folder` | `String` | 存档目录，默认 `psychenginemods` |

返回：无返回。

### flushSaveData(name:String)

把存档写入磁盘。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 存档名 |

返回：无返回。存档未初始化时红字提示。

### getDataFromSave(name:String, field:String, ?defaultValue:Dynamic = null)

读取存档里的一个字段。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 存档名 |
| `field` | `String` | 字段名 |
| `defaultValue` | `Dynamic` | 存档未初始化时返回的默认值 |

返回：字段值；存档不存在时返回 `defaultValue`。

### setDataFromSave(name:String, field:String, value:Dynamic)

写入存档字段。

返回：无返回。

### checkFileExists(filename:String, ?absolute:Bool = false)

判断文件是否存在。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `filename` | `String` | 相对路径（会先查 mod 目录，再查 `assets/`） |
| `absolute` | `Bool` | `true` 时把 `filename` 当成绝对路径 |

返回：`Bool`。

### saveFile(path:String, content:String, ?absolute:Bool = false)

写文件。相对路径写到 `mods/` 目录下。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `path` | `String` | 文件路径 |
| `content` | `String` | 写入内容 |
| `absolute` | `Bool` | `true` 时按绝对路径写入 |

返回：`Bool`，成功 `true`，异常 `false`（并红字报错）。

### deleteFile(path:String, ?ignoreModFolders:Bool = false)

删除文件。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `path` | `String` | 文件路径 |
| `ignoreModFolders` | `Bool` | `true` 时跳过 mod 目录查找，直接按资源路径删除 |

返回：`Bool`。

### getTextFromFile(path:String, ?ignoreModFolders:Bool = false)

把文本文件内容读成字符串。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `path` | `String` | 文件路径 |
| `ignoreModFolders` | `Bool` | 是否跳过 mod 目录查找 |

返回：`String` 文件内容。

### stringStartsWith(str:String, start:String)

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `str` | `String` | 原字符串 |
| `start` | `String` | 前缀 |

返回：`Bool`。

### stringEndsWith(str:String, end:String)

判断后缀。

返回：`Bool`。

### stringSplit(str:String, split:String)

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `str` | `String` | 原字符串 |
| `split` | `String` | 分隔符 |

返回：`Array<String>` 拆分结果。

### stringTrim(str:String)

去掉首尾空白。

返回：`String`。

### directoryFileList(folder:String)

列出目录下的文件与子目录名。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `folder` | `String` | 目录路径 |

返回：`Array<String>`；目录不存在时为空表。

### addRequirePath(path:String)

给脚本的 `require()` 增加一个搜索路径。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `path` | `String` | 追加的路径 |

返回：无返回。初始搜索路径是 `./`、`mods/`、`scripts/`、`data/`。

### clearRequireCache(?modname:String)

清空 `require()` 的模块缓存。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `modname` | `String` | 只清这一个模块；省略则全清 |

返回：无返回。

### getColorFromHex(color:String)

把十六进制颜色字符串转成整数颜色值。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `color` | `String` | 如 `'FF0000'`、`'0xFFFF0000'`；不带 `0x` 时自动补 `0xff` |

返回：`Int` 颜色值。

### getRandomInt(min:Int, max:Int = FlxMath.MAX_VALUE_INT, exclude:String = '')

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `min` | `Int` | 最小值 |
| `max` | `Int` | 最大值，默认极大值 |
| `exclude` | `String` | 逗号分隔的排除值，如 `'1,3,5'` |

返回：`Int` 随机整数。

### getRandomFloat(min:Float, max:Float = 1, exclude:String = '')

参数含义同 `getRandomInt`，`exclude` 为逗号分隔的浮点数。

返回：`Float` 随机浮点数。

### getRandomBool(chance:Float = 50)

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `chance` | `Float` | 返回 `true` 的百分比，默认 `50` |

返回：`Bool`。

### keyboardJustPressed(name:String)

直接查询 Flixel 键盘状态：按下瞬间。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | Flixel 按键字段名，如 `'SPACE'`、`'A'`、`'LEFT'` |

返回：`Bool`。

### keyboardPressed(name:String)

直接查询 Flixel 键盘状态：按住。

返回：`Bool`。

### keyboardReleased(name:String)

直接查询 Flixel 键盘状态：松开瞬间。

返回：`Bool`。

### anyGamepadJustPressed(name:String)

任意手柄上的某个按键是否刚刚按下。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 手柄按键名，如 `'A'`、`'DPAD_UP'` |

返回：`Bool`。

### anyGamepadPressed(name:String)

任意手柄上的某个按键是否按住。

返回：`Bool`。

### anyGamepadReleased(name:String)

任意手柄上的某个按键是否刚松开。

返回：`Bool`。

### gamepadAnalogX(id:Int, ?leftStick:Bool = true)

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `id` | `Int` | 手柄 ID |
| `leftStick` | `Bool` | `true` 读左摇杆，`false` 读右摇杆 |

返回：`Float` X 轴值；手柄不存在时返回 `0.0`。

### gamepadAnalogY(id:Int, ?leftStick:Bool = true)

同上，返回 Y 轴值；手柄不存在时返回 `0.0`。

### gamepadJustPressed(id:Int, name:String)

指定手柄的某个按键是否刚按下。

返回：`Bool`；手柄不存在时返回 `false`。

### gamepadPressed(id:Int, name:String)

指定手柄的某个按键是否按住。返回 `Bool`。

### gamepadReleased(id:Int, name:String)

指定手柄的某个按键是否刚松开。返回 `Bool`。

### keyJustPressed(name:String)

按**游戏内映射**（玩家按键绑定）查询「刚按下」。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 只支持 `'left'`、`'down'`、`'up'`、`'right'`、`'accept'`、`'back'`、`'pause'`、`'reset'`、`'space'`；其他名字恒为 `false` |

返回：`Bool`。

### keyPressed(name:String)

按游戏内映射查询「按住」。只支持 `'left'`、`'down'`、`'up'`、`'right'`、`'space'`。

返回：`Bool`。

### keyReleased(name:String)

按游戏内映射查询「刚松开」。只支持 `'left'`、`'down'`、`'up'`、`'right'`、`'space'`。

返回：`Bool`。

### mouseClicked(button:String)

鼠标按键是否刚点击。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `button` | `String` | `'left'`（默认，也匹配其他未列出的值）、`'middle'`、`'right'` |

返回：`Bool`。

### mousePressed(button:String)

鼠标按键是否按住。`button` 同 `mouseClicked`。

返回：`Bool`。

### mouseReleased(button:String)

鼠标按键是否刚松开。`button` 同 `mouseClicked`。

返回：`Bool`。

### getMouseX(camera:String)

鼠标在指定相机坐标系里的 X 位置。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `camera` | `String` | `'camGame'`（默认）、`'camHUD'`/`'hud'`、`'camOther'`/`'other'`、`'camVideo'`/`'video'` |

返回：`Float`。

### getMouseY(camera:String)

同上，返回 Y 位置。

返回：`Float`。

---

## 游戏控制函数

<!-- source: psych/script/FunkinLua.hx -->

本类控制歌曲流程、分数血量、判定、摄像机、角色位置、modchart 数值以及对话/视频。**本类共 50 个函数。**

### openCustomSubstate(name:String, pauseGame:Bool = false)

打开一个名为 `name` 的自定义子状态（`CustomSubstate`），并触发 `onCustomSubstateCreate(name)` 等回调。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 子状态名，回调里会作为参数传回 |
| `pauseGame` | `Bool` | `true` 时暂停 `PlayState` 与音乐 |

返回：无返回。

### closeCustomSubstate()

关闭自定义子状态。

参数：无。

返回：`Bool`，确实关闭了返回 `true`，没有打开的子状态返回 `false`。

### loadSong(?name:String = null, ?difficultyNum:Int = -1)

在游戏中重新加载一首歌（会走 `LoadingState` 切场景）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 歌曲名；`nil` 或空串时用当前歌曲 |
| `difficultyNum` | `Int` | 难度序号；`-1` 时用当前难度 |

返回：无返回。

### addScore(value:Int = 0)

给当前得分加上 `value`（可为负），随后重算评级。

返回：无返回。

### addMisses(value:Int = 0)

给丢失数加上 `value`，随后重算评级。返回：无返回。

### addHits(value:Int = 0)

给命中数加上 `value`，随后重算评级。返回：无返回。

### setScore(value:Int = 0)

直接设置得分，随后重算评级。返回：无返回。

### setMisses(value:Int = 0)

直接设置丢失数，随后重算评级。返回：无返回。

### setHits(value:Int = 0)

直接设置命中数，随后重算评级。返回：无返回。

### getScore()

返回：`Int` 当前得分。

### getMisses()

返回：`Int` 当前丢失数。

### getHits()

返回：`Int` 当前命中数。

### setHealth(value:Float = 0)

直接设置血量（`0`～`2`）。返回：无返回。

### addHealth(value:Float = 0)

增减血量。返回：无返回。

### getHealth()

返回：`Float` 当前血量。

### addCharacterToList(name:String, type:String)

把某个角色预加入角色加载列表，避免出场时卡顿。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 角色名（对应 `characters/<name>.json`） |
| `type` | `String` | `'dad'` 为对手，`'gf'` / `'girlfriend'` 为女友，其他值一律当作玩家（BF） |

返回：无返回。

### triggerEvent(name:String, arg1:Dynamic, arg2:Dynamic)

手动触发一个歌曲事件（等同在谱面里放该事件）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 事件名 |
| `arg1` | `Dynamic` | 第一个值（会转成 `String`） |
| `arg2` | `Dynamic` | 第二个值（会转成 `String`） |

返回：`Bool`，触发成功 `true`；菜单态下没有事件系统，打印提示并返回 `false`。

### startCountdown()

开始倒计时（用于对话/视频结束后接回歌曲）。

参数：无。

返回：`Bool`，恒为 `true`。

### addTouchPad(Dpad:String, Full:String)

添加屏幕虚拟按键（**仅 Android 构建注册**）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `Dpad` | `String` | D-Pad 模式枚举名 |
| `Full` | `String` | 动作键模式枚举名 |

返回：`Bool`，恒为 `true`。

### setPercent(modName:String, val:Float, player:Int = -1)

设置 modchart 数值（百分比形式）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `modName` | `String` | 修饰器名，如 `'scroll'`、`'alpha'` |
| `val` | `Float` | 目标值，默认含义是 0～1 的百分比 |
| `player` | `Int` | `0` 玩家、`1` 对手、`-1` 两者，默认 `-1` |

返回：无返回。

### addBlankMod(modName:String, defaultVal:Float = 0, player:Int = -1)

注册一个空的 SubModifier 修饰器，之后才能用 `queueEase` 等做补间。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `modName` | `String` | 修饰器名 |
| `defaultVal` | `Float` | 初始值 |
| `player` | `Int` | 玩家/对手，默认 `-1` |

返回：无返回。

### setValue(modName:String, val:Float, player:Int = -1)

以**原始值**语义设置修饰器（与 `setPercent` 的百分比语义对应）。

参数同 `setPercent`。返回：无返回。

### getPercent(modName:String, player:Int)

读取修饰器当前百分比值。

返回：`Float`。

### getValue(modName:String, player:Int)

读取修饰器当前原始值。返回：`Float`。

### queueSet(step:Float, modName:String, target:Float, player:Int = -1)

在第 `step` 步把修饰器设为目标值（瞬时）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `step` | `Float` | 目标步数 |
| `modName` | `String` | 修饰器名 |
| `target` | `Float` | 目标值 |
| `player` | `Int` | 播放者，默认 `-1` |

返回：无返回。

### queueSetP(step:Float, modName:String, perc:Float, player:Int = -1)

同 `queueSet`，但 `perc` 是百分比值。返回：无返回。

### queueEase(step:Float, endStep:Float, modName:String, percent:Float, style:String = 'linear', player:Int = -1, ?startVal:Float)

在 `step` 到 `endStep` 之间做缓动。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `step` | `Float` | 起始步 |
| `endStep` | `Float` | 结束步 |
| `modName` | `String` | 修饰器名 |
| `percent` | `Float` | 目标值 |
| `style` | `String` | 缓动名，默认 `'linear'` |
| `player` | `Int` | 播放者，默认 `-1` |
| `startVal` | `Float` | 可选起始值，省缺则用当前值 |

返回：无返回。

### queueEaseP(step:Float, endStep:Float, modName:String, percent:Float, style:String = 'linear', player:Int = -1, ?startVal:Float)

同 `queueEase`，但按百分比语义。返回：无返回。

### endSong()

立即结束歌曲（会先 `KillNotes()`）。

参数：无。

返回：`Bool`，恒为 `true`。

### restartSong(?skipTransition:Bool = false)

重开当前歌曲。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `skipTransition` | `Bool` | 是否跳过转场动画 |

返回：`Bool`，恒为 `true`。

### exitSong(?skipTransition:Bool = false)

退出歌曲回到选歌界面（剧情模式回 `StoryMenuState`，否则回 `FreeplayState`）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `skipTransition` | `Bool` | 是否跳过转场动画 |

返回：`Bool`，恒为 `true`。

### getSongPosition()

返回：`Float`，`Conductor.songPosition` 当前歌曲位置（毫秒）。

### getCharacterX(type:String)

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `type` | `String` | `'dad'` / `'opponent'`、`'gf'` / `'girlfriend'`，其他值一律当作玩家 |

返回：`Float`，对应角色组的 X。

### setCharacterX(type:String, value:Float)

设置角色组 X。`type` 规则同上。返回：无返回。

### getCharacterY(type:String)

返回：`Float`，对应角色组的 Y。

### setCharacterY(type:String, value:Float)

设置角色组 Y。返回：无返回。

### cameraSetTarget(target:String)

切换摄像机跟随对象。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `target` | `String` | 传 `'dad'` 跟对手，其他值跟玩家 |

返回：`Bool`，`true` 表示跟的是对手。

### cameraShake(camera:String, intensity:Float, duration:Float)

屏幕震动。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `camera` | `String` | 相机名，规则见 `getMouseX` |
| `intensity` | `Float` | 强度，原版示例用 `0.05` |
| `duration` | `Float` | 持续秒数 |

返回：无返回。

### cameraFlash(camera:String, color:String, duration:Float, forced:Bool)

屏幕闪白。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `camera` | `String` | 相机名 |
| `color` | `String` | 颜色十六进制串，如 `'FFFFFF'` |
| `duration` | `Float` | 持续秒数 |
| `forced` | `Bool` | 上一次闪光未播完时是否重开 |

返回：无返回。

### cameraFade(camera:String, color:String, duration:Float, forced:Bool)

屏幕渐隐到指定颜色。参数含义同 `cameraFlash`。返回：无返回。

### setRatingPercent(value:Float)

设置评级百分比（`0`～`1`）。返回：无返回。

### setRatingName(value:String)

设置评级名称（如 `'Sick!!'`）。返回：无返回。

### setRatingFC(value:String)

设置 FC 标签（如 `'SFC'`）。返回：无返回。

### characterDance(character:String)

让某个角色跳一次 idle 舞。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `character` | `String` | `'dad'`、`'gf'` / `'girlfriend'`，其他值一律当作玩家 |

返回：无返回。

### setHealthBarColors(leftHex:String, rightHex:String, ?rightHex2:String)

设置血条左右颜色。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `leftHex` | `String` | 左侧颜色十六进制串 |
| `rightHex` | `String` | 右侧颜色十六进制串 |
| `rightHex2` | `String` | **Parker 扩展重载**：给了第三个参数时按 `setHealthBarColors(barTag, leftHex, rightHex)` 解释，作用于 `makeHealthBar` 创建的自定义血条（详见 `lua-es-extensions.md`） |

返回：无返回。菜单态且未给第三参数时直接返回，不做任何事。

### setTimeBarColors(leftHex:String, rightHex:String)

设置时间条颜色。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `leftHex` | `String` | 左色 |
| `rightHex` | `String` | 右色（注意源码里左右是反着 `createFilledBar(right, left)` 传的） |

返回：无返回。

### startDialogue(dialogueFile:String, music:String = null)

开始一段对话。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `dialogueFile` | `String` | 对话 JSON 文件名，读取 `data/<格式化歌名>/<文件名>` |
| `music` | `String` | 可选背景音乐名（`music/` 下的 ogg） |

返回：`Bool`，成功解析并开始返回 `true`；文件缺失或格式错误返回 `false`（此时若正在收尾就 `endSong()`，否则 `startCountdown()`）。触发的回调是 `onNextDialogue` / `onSkipDialogue`。

### startVideo(videoFile:String, ?forMidSong:Bool = false)

播放一段视频。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `videoFile` | `String` | 视频文件名（`videos/` 下的 mp4） |
| `forMidSong` | `Bool` | `true` 表示歌中途播放（会解除 `inCutscene` 并允许暂停） |

返回：`Bool`，文件存在并开始播放返回 `true`，文件不存在返回 `false`。若平台没编译 `VIDEOS_ALLOWED`，直接 `endSong()` 或 `startCountdown()` 并返回 `true`。

### camFollowPos(x:Float = 0, y:Float = 0)

**只在菜单脚本（`LuaSState`）里注册。** 把菜单相机滚动到让内容坐标 `(x, y)` 落在屏幕中心（菜单相机默认滚动了半屏，所以内容原点 `(0, 0)` 就是屏幕中心）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `x` | `Float` | 目标内容 X |
| `y` | `Float` | 目标内容 Y |

返回：无返回。

### camFollow(x:Float = 0, y:Float = 0)

**只在菜单脚本里注册。** 与 `camFollowPos` 行为完全一致（源码里是两个同体函数）。

返回：无返回。

---

## 对象 / 精灵 / 文本函数

<!-- source: psych/script/FunkinLua.hx -->

本类包含属性读写、对象创建/动画/图层、精灵、Lua 纯文本与 Lua 视频精灵。**本类共 66 个函数。**

### loadGraphic(variable:String, image:String, ?gridX:Int = 0, ?gridY:Int = 0)

给已有精灵换贴图。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `variable` | `String` | 目标对象路径，支持 `'a.b.c'` 逐层取值 |
| `image` | `String` | 图片路径（相对 `images/`） |
| `gridX` | `Int` | 网格宽；非 0 即启用动画帧网格 |
| `gridY` | `Int` | 网格高 |

返回：无返回。

### loadFrames(variable:String, image:String, spriteType:String = "sparrow")

给已有精灵换整套帧。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `variable` | `String` | 目标对象路径 |
| `image` | `String` | 图集名 |
| `spriteType` | `String` | `'sparrow'`（默认）、`'packer'` / `'packeratlas'` / `'pac'`、`'texture'` / `'textureatlas'` / `'tex'`（Animate Atlas）、`'texture_noaa'`、`'tex_noaa'`（不带抗锯齿） |

返回：无返回。

### getProperty(variable:String)

读取对象属性（支持 `'boyfriend.x'` 这类点号路径，也支持 `'arr[3]'` 下标写法）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `variable` | `String` | 属性路径 |

返回：属性值（`Dynamic`）。

### setProperty(variable:String, value:Dynamic)

写入对象属性。参数同上，另加要写入的 `value`。

返回：`Bool`，恒为 `true`。

### getPropertyFromGroup(obj:String, index:Int, variable:Dynamic)

读取组/数组里第 `index` 个成员的属性。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 组名（`FlxTypedGroup` 或数组），支持点号路径 |
| `index` | `Int` | 成员下标 |
| `variable` | `Dynamic` | 属性名；传 `Int` 时按数组下标处理 |

返回：属性值；找不到成员时红字提示并返回 `null`。

### setPropertyFromGroup(obj:String, index:Int, variable:Dynamic, value:Dynamic)

写入组成员属性。参数同上，另加 `value`。

返回：无返回。

### removeFromGroup(obj:String, index:Int, dontDestroy:Bool = false)

从组里移除成员。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 组名 |
| `index` | `Int` | 下标 |
| `dontDestroy` | `Bool` | `false`（默认）时先 `kill()` 并 `destroy()`，`true` 时只移除 |

返回：无返回。

### getPropertyFromClass(classVar:String, variable:String)

读取某个类（或实例）的静态属性，支持点号路径。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `classVar` | `String` | 类名，如 `'ClientPrefs'`、`'PlayState'` |
| `variable` | `String` | 属性路径 |

返回：属性值。

### setPropertyFromClass(classVar:String, variable:String, value:Dynamic)

写入类属性。返回：`Bool`，恒为 `true`。

### callMethod(funcToRun:String, ?args:Array<Dynamic> = null)

调用 `PlayState` 上的方法。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `funcToRun` | `String` | 方法名，支持点号逐层取值 |
| `args` | `Array` | 参数表；参数可用 `instanceArg()` 包装成对象/类引用（见 `createInstance`） |

返回：被调用方法的返回值（`null` 表示找不到方法）。

### callMethodFromClass(className:String, funcToRun:String, ?args:Array<Dynamic> = null)

调用某个类上的静态方法。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `className` | `String` | 类名 |
| `funcToRun` | `String` | 方法名 |
| `args` | `Array` | 参数表 |

返回：被调用方法的返回值。

### createInstance(variableToSave:String, className:String, ?args:Array<Dynamic> = null)

创建一个 Haxe 类的实例并存进变量表。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `variableToSave` | `String` | 存放实例的变量名（点号会被去掉） |
| `className` | `String` | 类名 |
| `args` | `Array` | 构造参数 |

返回：`Bool`，创建成功 `true`。变量名已存在、类不存在或构造失败都会红字提示并返回 `false`。

### addInstance(objectName:String, ?inFront:Bool = false)

把 `createInstance` 创建的实例加进场景。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `objectName` | `String` | 变量名 |
| `inFront` | `Bool` | `true` 直接 `add` 到最前；`false` 插到角色组之前（死亡时插到 `GameOverSubstate` 的 BF 之前） |

返回：无返回。变量不存在时红字提示。

### instanceArg(instanceName:String, ?className:String = null)

生成一个「实例/类引用」字符串，供 `callMethod` / `callMethodFromClass` 的参数传递对象。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `instanceName` | `String` | 变量名或属性路径 |
| `className` | `String` | 指明要解析成这个类而不是实例 |

返回：`String`，形如 `##PSYCHLUA_STRINGTOOBJ::name::Class` 的占位串。

### getObjectOrder(obj:String)

读取对象在场景里的绘制顺序。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 对象路径 |

返回：`Int` 下标；对象不存在时红字提示并返回 `-1`。

### setObjectOrder(obj:String, position:Int)

把对象移动到指定绘制顺序。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 对象路径 |
| `position` | `Int` | 目标下标 |

返回：无返回。

### getMidpointX(variable:String)

读取对象中点（含缩放/偏移）的 X。

返回：`Float`；对象不存在时返回 `0`。

### getMidpointY(variable:String)

同上，返回 Y。

### getGraphicMidpointX(variable:String)

读取对象图形中点的 X。返回：`Float`，找不到返回 `0`。

### getGraphicMidpointY(variable:String)

同上，返回 Y。

### getScreenPositionX(variable:String)

读取对象在屏幕上的 X。返回：`Float`，找不到返回 `0`。

### getScreenPositionY(variable:String)

同上，返回 Y。

### makeLuaSprite(tag:String, image:String, x:Float, y:Float, ?sfX:Null<Float>, ?sfY:Null<Float>, ?p7:Dynamic)

创建一个 Lua 精灵（**必须再 `addLuaSprite` 才会显示**）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 精灵 tag（点号会被去掉），同名会先销毁旧的 |
| `image` | `String` | 图片路径，可为 `nil` 创建空白精灵 |
| `x` / `y` | `Float` | 位置 |
| `sfX` / `sfY` | `Float` | **Parker 扩展**：仅菜单态生效，设置 `scrollFactor`（默认 `1`） |
| `p7` | `Dynamic` | 预留参数，源码中未使用 |

返回：无返回。**Parker 行为**：若 `images/<image>.xml` 存在，会自动按 Sparrow 图集加载（原版 Psych 只当单图）。

### makeAnimatedLuaSprite(tag:String, image:String, x:Float, y:Float, ?spriteType:String = "sparrow")

创建带帧动画的 Lua 精灵。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | tag |
| `image` | `String` | 图集名 |
| `x` / `y` | `Float` | 位置 |
| `spriteType` | `String` | 同 `loadFrames` 的取值 |

返回：无返回。

### makeGraphic(obj:String, width:Int, height:Int, color:String)

把对象填充成纯色矩形。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 目标对象路径（先查 Lua 精灵，再查场景对象） |
| `width` / `height` | `Int` | 尺寸 |
| `color` | `String` | 十六进制颜色串 |

返回：无返回。

### addAnimationByPrefix(obj:String, name:String, prefix:String, framerate:Int = 24, loop:Bool = true)

按前缀添加动画；若对象当前没有动画，会立刻播放新加的这个。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 目标对象 |
| `name` | `String` | 动画名 |
| `prefix` | `String` | 帧名前缀 |
| `framerate` | `Int` | 帧率，默认 `24` |
| `loop` | `Bool` | 是否循环，默认 `true` |

返回：无返回。

### addAnimation(obj:String, name:String, frames:Array<Int>, framerate:Int = 24, loop:Bool = true)

按帧下标数组添加动画。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `frames` | `Array<Int>` | 帧下标列表 |

其余参数同 `addAnimationByPrefix`。返回：无返回。

### addAnimationByIndices(obj:String, name:String, prefix:String, indices:String, framerate:Int = 24)

按 `indices` 里逗号分隔的帧号，从指定前缀里挑帧组成动画（不循环）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `indices` | `String` | 逗号分隔的帧号，如 `'0,2,4'`；会先 `trim()` |
| 其他 | — | 同上 |

返回：`Bool`，找到并添加成功 `true`。

### addAnimationByIndicesLoop(obj:String, name:String, prefix:String, indices:String, framerate:Int = 24)

同 `addAnimationByIndices`，但循环播放。

返回：`Bool`。

### playAnim(obj:String, name:String, forced:Bool = false, ?reverse:Bool = false, ?startFrame:Int = 0)

播放动画，同时兼容精灵、角色与 Lua 精灵。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 目标对象 |
| `name` | `String` | 动画名；对手里没有这个动画则什么都不做 |
| `forced` | `Bool` | 强制重播，默认 `false` |
| `reverse` | `Bool` | 倒放 |
| `startFrame` | `Int` | 起始帧 |

返回：`Bool`，找到对象返回 `true`，找不到返回 `false`。若目标是 `Character` 会走 `Character.playAnim()`（带角色偏移与 sing 时长逻辑）；若是 Lua 精灵会应用 `addOffset` 记录的动画偏移。

### addOffset(obj:String, anim:String, x:Float, y:Float)

给某个动画设置偏移。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 目标（Lua 精灵或角色） |
| `anim` | `String` | 动画名 |
| `x` / `y` | `Float` | 偏移量 |

返回：`Bool`，成功 `true`。

### setScrollFactor(obj:String, scrollX:Float, scrollY:Float)

设置滚动视差系数。

返回：无返回。

### addLuaSprite(tag:String, front:Bool = false)

把 `makeLuaSprite` 创建的精灵加进场景（只会加一次）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 精灵 tag |
| `front` | `Bool` | `true` 加到最前；`false` 插到 GF/BF/DAD 三个角色组中最靠前的位置之前（死亡时插到 `GameOverSubstate` 的 BF 前） |

返回：无返回。

### setGraphicSize(obj:String, x:Int, y:Int = 0, updateHitbox:Bool = true)

设置图形尺寸。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `x` | `Int` | 宽；传 `0` 表示按高度等比 |
| `y` | `Int` | 高；默认 `0` |
| `updateHitbox` | `Bool` | 是否同步碰撞箱，默认 `true` |

返回：无返回。对象不存在时红字提示。

### scaleObject(obj:String, x:Float, y:Float, updateHitbox:Bool = true)

设置缩放倍率。

返回：无返回。对象不存在时红字提示。

### updateHitbox(obj:String)

刷新碰撞箱。返回：无返回。

### updateHitboxFromGroup(group:String, index:Int)

刷新组内某个成员的碰撞箱。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `group` | `String` | 组名 |
| `index` | `Int` | 下标 |

返回：无返回。

### removeLuaSprite(tag:String, destroy:Bool = true)

移除 Lua 精灵。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 精灵 tag |
| `destroy` | `Bool` | `true`（默认）时 `kill()` + `destroy()` 并从注册表删除；`false` 只从场景移除、保留对象 |

返回：无返回。tag 不存在时直接返回。

### luaSpriteExists(tag:String)

返回：`Bool`，Lua 精灵注册表里是否有该 tag。

### luaTextExists(tag:String)

返回：`Bool`，Lua 文本注册表里是否有该 tag。

### setObjectCamera(obj:String, camera:String = '')

设置对象只由某台相机渲染。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 对象路径 |
| `camera` | `String` | 相机名（同 `getMouseX`），默认 `camGame` |

返回：`Bool`，成功 `true`。对象不存在时红字提示并返回 `false`。

### setBlendMode(obj:String, blend:String = '')

设置混合模式。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 对象路径 |
| `blend` | `String` | `'add'`、`'alpha'`、`'darken'`、`'difference'`、`'erase'`、`'hardlight'`、`'invert'`、`'layer'`、`'lighten'`、`'multiply'`、`'overlay'`、`'screen'`、`'shader'`、`'subtract'`；其他值一律 `normal` |

返回：`Bool`，成功 `true`。

### screenCenter(obj:String, pos:String = 'xy')

把对象居中到屏幕。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 对象路径 |
| `pos` | `String` | `'x'`、`'y'`、其他值（含默认 `'xy'`）表示同时居中 |

返回：无返回。

### objectsOverlap(obj1:String, obj2:String)

检测两个对象是否重叠。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj1` / `obj2` | `String` | 对象路径（先查 Lua 对象，再查场景对象） |

返回：`Bool`；任一对象为 `null` 时返回 `false`。

### getPixelColor(obj:String, x:Int, y:Int)

取对象某像素的颜色。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 对象路径 |
| `x` / `y` | `Int` | 像素坐标 |

返回：`Int` 颜色值（源调用 `getPixel32` 但没 return，实际取的是 `spr.pixels.getPixel32(x, y)`）；对象不存在返回 `0`。

### makeLuaVideoSprite(tag:String, ?path:String = null, ?x:Float = 0, ?y:Float = 0, ?destroyOnUse = true)

创建 Lua 视频精灵（只能在歌曲中创建）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | tag |
| `path` | `String` | 视频文件（`videos/` 下的 mp4），可为空 |
| `x` / `y` | `Float` | 位置（在 `onFormat` 回调里才会写入） |
| `destroyOnUse` | `Bool` | 播放结束后是否自动销毁 |

返回：无返回。会自动触发 `onVideoFormat(tag)` / `onVideoStart(tag)` / `onVideoFinished(tag)`。

### playVideo(tag:String)

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 视频 tag |

返回：无返回（tag 不存在时不做事）。

### stopVideo(tag:String)

停止视频播放。返回：无返回。

### EndVideo(tag:String)

销毁视频精灵。返回：无返回。

### resumeVideo(tag:String)

继续播放。返回：无返回。

### pauseVideo(tag:String)

暂停播放。返回：无返回。

### makeLuaText(tag:String, text:String, width:Int, x:Float, y:Float)

创建 Lua 文本（默认字体 `vcr.ttf`、字号 16、白色、居中、黑色描边 2、宽度会 `fieldWidth`）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | tag，点号会被去掉，同名先销毁旧文本 |
| `text` | `String` | 初始内容 |
| `width` | `Int` | 文本域宽度 |
| `x` / `y` | `Float` | 位置 |

返回：无返回。

### setTextString(tag:String, text:String)

设置文本内容。返回：`Bool`，成功 `true`。

### setTextSize(tag:String, size:Int)

设置字号。返回：`Bool`。

### setTextWidth(tag:String, width:Float)

设置文本域宽度（`fieldWidth`）。返回：`Bool`。

### setTextBorder(tag:String, size:Dynamic, color:Dynamic)

设置描边。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 文本 tag |
| `size` | `Dynamic` | 描边宽度；**若这里传的是字符串而 `color` 不是字符串，两者会自动交换**（兼容 Engine Custom ES 的 `setTextBorder(tag, color, size)` 调用顺序） |
| `color` | `Dynamic` | 描边颜色，十六进制串 |

返回：`Bool`。

### setTextColor(tag:String, color:String)

设置文字颜色。返回：`Bool`。

### setTextFont(tag:String, newFont:String)

设置字体（走 `Paths.fontName`，所以传字体文件名，如 `'vcr.ttf'`）。返回：`Bool`。

### setTextItalic(tag:String, italic:Bool)

设置斜体。返回：`Bool`。

### setTextAlignment(tag:String, alignment:String = 'left')

设置对齐。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `alignment` | `String` | `'right'`、`'center'`，其他值（含默认 `'left'`）为左对齐 |

返回：`Bool`。

### getTextString(tag:String)

返回：`String` 文本内容；找不到返回 `null`。

### getTextSize(tag:String)

返回：`Int` 字号；找不到返回 `-1`。

### getTextFont(tag:String)

返回：`String` 字体名；找不到返回 `null`。

### getTextWidth(tag:String)

返回：`Float` 文本域宽度；找不到返回 `0`。

### addLuaText(tag:String)

把 Lua 文本加进场景（只会加一次）。返回：无返回。

### removeLuaText(tag:String, destroy:Bool = true)

移除 Lua 文本。参数与 `removeLuaSprite` 一致。

返回：无返回。

---

## 补间与计时器函数

<!-- source: psych/script/FunkinLua.hx -->

**本类共 16 个函数。** 缓动名（`ease` 参数）可取：`linear`、`quadIn/Out/InOut`、`quartIn/Out/InOut`、`quintIn/Out/InOut`、`sineIn/Out/InOut`、`expoIn/Out/InOut`、`circIn/Out/InOut`、`cubeIn/Out/InOut`、`backIn/Out/InOut`、`elasticIn/Out/InOut`、`bounceIn/Out/InOut`、`smoothStepIn/InOut/Out`、`smootherStepIn/InOut/Out`；无法识别时一律按 `linear`。

### startTween(tag:String, vars:String, values:Any = null, duration:Float, options:Any = null)

给任意对象的任意属性做补间（最通用的 tween 入口）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 补间 tag，用于 `cancelTween`；同名会先取消旧的 |
| `vars` | `String` | 目标对象路径，如 `'bg'`、`'boyfriend'` |
| `values` | `Table` | 属性表，如 `{x = 100, alpha = 0.5}` |
| `duration` | `Float` | 时长（秒） |
| `options` | `Table` | 可选表：`type`（`'backward'`/`'loop'`/`'pingpong'`/`'persist'`，其他为 `oneshot`）、`ease`、`startDelay`、`loopDelay`、`onUpdate`（字符串回调名）、`onStart`、`onComplete`（都会以 `(tag, vars)` 调用） |

返回：无返回。`values` 为空时红字提示「No values on 2nd argument!」。

### doTweenX(tag:String, vars:String, value:Dynamic, duration:Float, ease:String)

把对象 X 补间到 `value`，完成后触发 `onTweenCompleted(tag)`。

参数含义同上。返回：无返回。

### doTweenY(tag:String, vars:String, value:Dynamic, duration:Float, ease:String)

同上，补间 Y。返回：无返回。

### doTweenAngle(tag:String, vars:String, value:Dynamic, duration:Float, ease:String)

补间 `angle`。返回：无返回。

### doTweenAlpha(tag:String, vars:String, value:Dynamic, duration:Float, ease:String)

补间 `alpha`。返回：无返回。

### doTweenZoom(tag:String, vars:String, value:Dynamic, duration:Float, ease:String)

补间相机 `zoom`。返回：无返回。

### doTweenNum(tag:String, value1:Dynamic, value2:Dynamic, duration:Float, ease:String)

在 `value1` 与 `value2` 之间补间一个纯数字，每次更新触发 `onTweenUpdateNum(tag, num)`。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `value1` | `Dynamic` | 起始值 |
| `value2` | `Dynamic` | 结束值 |

返回：无返回。

### doTweenColor(tag:String, vars:String, targetColor:String, duration:Float, ease:String)

把对象 `color` 补间到目标颜色。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `targetColor` | `String` | 目标颜色；不带 `0x` 前缀时会自动补 `0xff` |

返回：无返回。完成后同样触发 `onTweenCompleted(tag)`。

### noteTweenX(tag:String, note:Int, value:Dynamic, duration:Float, ease:String)

把第 `note` 个 strum（音符条）补间到 X。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `note` | `Int` | strum 下标；负数取 0，超出长度按 `% strumLineNotes.length` 取模 |
| `value` | `Dynamic` | 目标 X |

返回：无返回。仅歌曲中可用，菜单态会红字提示。

### noteTweenY(tag:String, note:Int, value:Dynamic, duration:Float, ease:String)

同上，补间 Y。返回：无返回。

### noteTweenAngle(tag:String, note:Int, value:Dynamic, duration:Float, ease:String)

同上，补间 `angle`。返回：无返回。

### noteTweenDirection(tag:String, note:Int, value:Dynamic, duration:Float, ease:String)

同上，补间 `direction`（音符条上下方向）。返回：无返回。

### noteTweenAlpha(tag:String, note:Int, value:Dynamic, duration:Float, ease:String)

同上，补间 `alpha`。返回：无返回。

### cancelTween(tag:String)

取消并销毁某个 tag 的补间。它同时会清掉 `startTween` 存在 `MusicBeatState` 变量表里 `tween_<tag>` 下的那条。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 补间 tag |

返回：无返回。

### runTimer(tag:String, time:Float = 1, loops:Int = 1)

启动一个计时器（会先取消同名计时器）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 计时器 tag |
| `time` | `Float` | 间隔秒数，默认 `1` |
| `loops` | `Int` | 循环次数，默认 `1`；`0` 表示无限循环 |

返回：无返回。每次触发都会回调 `onTimerCompleted(tag, loops, loopsLeft)`。

### cancelTimer(tag:String)

取消并销毁某个 tag 的计时器。返回：无返回。

---

## Shader 函数

<!-- source: psych/script/FunkinLua.hx -->

**本类共 16 个函数。** 全部依赖 `ClientPrefs.shaders` 为真；在 `flash` 平台或未启用 `MODS_ALLOWED`/`sys` 的构建里，读写函数会红字提示并返回 `null`（不支持），设置函数直接不做事。着色器文件放在 `shaders/<名字>.frag` 与 `.vert`（当前 mod 目录优先，其次全局 mod，最后 `assets/preload/shaders/`）。

### initLuaShader(name:String)

加载一套 `shaders/<name>.frag` + `.vert`。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 着色器名（不带扩展名） |

返回：`Bool`，加载成功或已经加载过返回 `true`。菜单态下不工作（内部要求有 `PlayState`）。

### setSpriteShader(obj:String, shader:String)

把已加载的着色器挂到对象上。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 对象路径 |
| `shader` | `String` | 着色器名；未加载会自动尝试 `initLuaShader` |

返回：`Bool`，成功 `true`。菜单态或没有 `PlayState` 时红字提示并返回 `false`。

### removeSpriteShader(obj:String)

摘掉对象的着色器。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 对象路径 |

返回：`Bool`，找到对象返回 `true`。

### getShaderBool(obj:String, prop:String)

读着色器里的 `bool` uniform。`obj` 是**挂载了着色器的对象路径**（不是着色器名）。

返回：`Bool`；对象或着色器不存在返回 `null`。

### getShaderBoolArray(obj:String, prop:String)

读 `bool` 数组 uniform。返回：数组或 `null`。

### getShaderInt(obj:String, prop:String)

读 `int` uniform。返回：`Int` 或 `null`。

### getShaderIntArray(obj:String, prop:String)

读 `int` 数组 uniform。返回：数组或 `null`。

### getShaderFloat(obj:String, prop:String)

读 `float` uniform。返回：`Float` 或 `null`。

### getShaderFloatArray(obj:String, prop:String)

读 `float` 数组 uniform。返回：数组或 `null`。

### setShaderBool(obj:String, prop:String, value:Bool)

写 `bool` uniform。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 已挂着色器的对象路径 |
| `prop` | `String` | uniform 名 |
| `value` | `Bool` | 值 |

返回：无返回。

### setShaderBoolArray(obj:String, prop:String, values:Dynamic)

写 `bool` 数组 uniform（`values` 为数组）。返回：无返回。

### setShaderInt(obj:String, prop:String, value:Int)

写 `int` uniform。返回：无返回。

### setShaderIntArray(obj:String, prop:String, values:Dynamic)

写 `int` 数组 uniform。返回：无返回。

### setShaderFloat(obj:String, prop:String, value:Float)

写 `float` uniform。返回：无返回。

### setShaderFloatArray(obj:String, prop:String, values:Dynamic)

写 `float` 数组 uniform。返回：无返回。

### setShaderSampler2D(obj:String, prop:String, bitmapdataPath:String)

给采样器 uniform 绑定一张图片。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 已挂着色器的对象路径 |
| `prop` | `String` | 采样器 uniform 名 |
| `bitmapdataPath` | `String` | 图片路径（走 `Paths.image`） |

返回：无返回。图片不存在（或 bitmap 为 `null`）时静默跳过。

---

## HScript 与 Haxe

<!-- source: psych/script/FunkinLua.hx -->

**本类共 2 个函数。** 它们把 HScript 解释器接进 Lua 脚本；构建里没开 `hscript` 时只会打印「HScript isn't supported on this platform!」。

### runHaxeCode(codeToRun:String)

在当前脚本里执行一段 HScript 代码。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `codeToRun` | `String` | HScript 源码 |

返回：`Bool` / `Int` / `Float` / `String` / `Array` 之一；返回值不属于这几种类型时返回 `null`。出错会在脚本调试文字里红字报出。

### addHaxeLibrary(libName:String, ?libPackage:String = '')

把一个 Haxe 类导入 HScript 的变量表。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `libName` | `String` | 类名 |
| `libPackage` | `String` | 包名，为空时按无包处理 |

返回：无返回。

---

## 回调模板

<!-- source: psych/script/FunkinLua.hx -->

脚本里按**名字**定义这些函数即可，引擎会在对应时机调用。它们不是 `set()` 注册的 Lua 函数，所以没有参数表和返回值；这里列出的是引擎**真正分发过**的回调及其参数（表中一行写了多个名字的表示它们共享同一行说明）。返回值约定见本页开头的常量说明。**共 54 个回调名。**

| 回调 | 参数 | 触发时机 |
| --- | --- | --- |
| `onCreate()` | 无 | 脚本创建完成、所有函数注册好、脚本体执行完之后（游戏脚本在 `FunkinLua` 构造末尾，菜单脚本在 `LuaSState.create()` 里、相机布局就位后） |
| `onCreatePost()` | 无 | `PlayState.create()` 的 `super.create()` 之后 |
| `onLoad()` | 无 | 歌曲脚本创建后（`PlayState.create()`），菜单脚本在 `LuaSState` 构造时 |
| `onUpdate(elapsed:Float)` | `elapsed` 帧间隔秒数 | 每帧 |
| `onUpdatePost(elapsed:Float)` | 同上 | 每帧，`super.update()` 之后 |
| `onStepHit()` | 无（读 `curStep`） | 每步 |
| `onBeatHit()` | 无（读 `curBeat`） | 每拍 |
| `onSectionHit()` | 无（读 `curSection`） | 每个小节 |
| `onStartCountdown()` | 无 | 倒计时开始前 |
| `onCountdownStarted()` | 无 | 倒计时开始 |
| `onCountdownTick(swagCounter:Int)` | 当前倒计时序号 | 倒计时每一 tick |
| `onSongStart()` | 无 | 歌曲正式开始（倒计时结束后） |
| `onEndSong()` | 无 | 歌曲结束 |
| `onGameOver()` | 无 | 触发 Game Over |
| `onGameOverStart()` | 无 | `GameOverSubstate` 创建时 |
| `onGameOverConfirm(isRetry:Bool)` | `true` 为重试 | 玩家在 Game Over 界面确认/放弃 |
| `onPause()` | 无 | 暂停时（`callOnScriptAll`，Lua 也收到） |
| `onResume()` | 无 | 取消暂停时 |
| `onDestroy()` | 无 | 脚本被停止/场景销毁（`PlayState.destroy()` 与 `LuaSState.destroy()` 直接调用） |
| `onDestroyPost()` | 无 | `onDestroy()` 未返回 `Function_Stop` 时（仅菜单脚本） |
| `onEvent(eventName:String, value1:String, value2:String)` | 事件名与两个值 | 歌曲事件触发 |
| `onEventSet(curStep:Int)` | 当前步数 | 每一步（菜单脚本也派发，用于 ES 的 `stepEvent()`） |
| `eventEarlyTrigger(eventName:String, value1:String, value2:String, strumTime:Float)` | 事件与目标时间 | 事件提前触发判定；**返回一个数值**即可提前触发，返回 `Function_Continue` 表示不处理 |
| `onSpawnNote(index:Int, noteData:Int, noteType:String, isSustainNote:Bool)` | 音符下标/方向/类型/是否长按 | 音符生成时 |
| `goodNoteHit(index:Int, noteData:Int, noteType:String, isSustainNote:Bool)` | 同上 | 玩家命中音符 |
| `opponentNoteHit(index:Int, noteData:Int, noteType:String, isSustainNote:Bool)` | 同上 | 对手命中音符 |
| `noteMiss(index:Int, noteData:Int, noteType:String, isSustainNote:Bool)` | 同上 | 漏接音符 |
| `noteMissPress(direction:Int)` | 按下的方向 | 空按（无音符可打） |
| `onGhostTap(key:Int)` | 按键方向 | 幽灵点击（受 `ghostTapping` 影响） |
| `onKeyPress(key:Int)` / `onKeyRelease(key:Int)` | 按键方向 | 按下/松开音符键 |
| `onUpdateScore(miss:Bool)` | 是否算漏接 | 分数变化时 |
| `onRecalculateRating()` | 无 | 重算评级时（`ignoreStops = false`，可以被中断） |
| `onMoveCamera(target:String)` | `'boyfriend'` / `'dad'` / `'gf'` | 摄像机切换跟随目标 |
| `onNextDialogue(dialogueCount:Int)` | 对话序号 | 进入下一句对话 |
| `onSkipDialogue(dialogueCount:Int)` | 对话序号 | 跳过对话 |
| `onCustomSubstateCreate(name:String)` | 子状态名 | `openCustomSubstate` 创建后 |
| `onCustomSubstateCreatePost(name:String)` | 子状态名 | 子状态 `super.create()` 之后 |
| `onCustomSubstateUpdate(name:String, elapsed:Float)` | 子状态名、帧间隔 | 子状态每帧 |
| `onCustomSubstateUpdatePost(name:String, elapsed:Float)` | 同上 | 子状态 `super.update()` 之后 |
| `onCustomSubstateDestroy(name:String)` | 子状态名 | 子状态销毁 |
| `preModifierRegister()` / `postModifierRegister()` | 无 | modchart 修饰器注册前后 |
| `generateModchart()` | 无 | 倒计时开始时生成 modchart |
| `onUpdateOptions(elapsed:Float)` | 帧间隔 | **仅菜单脚本**（`LuaSState.update`）每帧 |
| `onTweenCompleted(tag:String)` | 补间 tag | `doTweenX/Y/Angle/Alpha/Zoom/Color` 完成 |
| `onTweenUpdateNum(tag:String, num:Dynamic)` | 补间 tag、当前数值 | `doTweenNum` 每次更新 |
| `onTimerCompleted(tag:String, loops:Int, loopsLeft:Int)` | 计时器 tag、总次数、剩余次数 | `runTimer` 触发 |
| `onSoundFinished(tag:String)` | 音效 tag | 带 tag 的 `playSound` 播完 |
| `onVideoFormat(tag:String)` / `onVideoStart(tag:String)` / `onVideoFinished(tag:String)` | 视频 tag | `makeLuaVideoSprite` 的格式化/开始/结束 |
| `onPlayAnim(tag:String, anim:String)` | 角色 tag（`'boyfriend'`/`'dad'`/`'gf'` 或 `makeChar` 的 tag）、动画名 | **Parker 扩展**：`ESCompat.tick()` 在每帧 `onUpdate` 前检测到角色换了动画时派发 |
| `onTyping(tag:String)` | 文本 tag | **Parker 扩展**：`setTextSpeed` 打字机的每个字符 |

> 注意：`popUpScore` 与 `SkinNoteSplash` 在本分支里只走 `callOnScripts()`，**不会**分发给 Lua 脚本，所以此处不列出。

---

## 弃用函数

<!-- source: psych/script/FunkinLua.hx -->

**本类共 13 个函数。** 它们仍在注册表里可用（仅为向后兼容），但每次调用都会在脚本调试文字里打印 `xxx is deprecated! Use yyy instead`；把脚本全局 `luaDeprecatedWarnings` 设为 `false` 可以关掉这些提示。

### objectPlayAnimation(obj:String, name:String, forced:Bool = false, ?startFrame:Int = 0)

未使用的旧版播动画入口。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `obj` | `String` | 目标对象路径 |
| `name` | `String` | 动画名 |
| `forced` | `Bool` | 强制重播 |
| `startFrame` | `Int` | 起始帧 |

返回：`Bool`，找到对象 `true`。**替代写法：`playAnim(obj, name, forced)`**——注意旧版不会走 `Character.playAnim()`，对角色来说行为比新版更粗。

### characterPlayAnim(character:String, anim:String, ?forced:Bool = false)

未使用的旧版角色播动画入口。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `character` | `String` | `'dad'`、`'gf'` / `'girlfriend'`，其他值一律当作玩家 |
| `anim` | `String` | 动画名；角色偏移表里没有这个动画就什么都不做 |
| `forced` | `Bool` | 强制重播 |

返回：无返回。**替代写法：`playAnim(character, anim, forced)`**。

### luaSpriteMakeGraphic(tag:String, width:Int, height:Int, color:String)

给 Lua 精灵填充纯色矩形。

返回：无返回。**替代写法：`makeGraphic(tag, width, height, color)`**；区别是旧版只认 Lua 精灵注册表里的 tag。

### luaSpriteAddAnimationByPrefix(tag:String, name:String, prefix:String, framerate:Int = 24, loop:Bool = true)

给 Lua 精灵按前缀加动画。

返回：无返回。**替代写法：`addAnimationByPrefix(tag, name, prefix, framerate, loop)`**。

### luaSpriteAddAnimationByIndices(tag:String, name:String, prefix:String, indices:String, framerate:Int = 24)

给 Lua 精灵按帧号列表加动画（不循环）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `indices` | `String` | 逗号分隔的帧号 |

返回：无返回。**替代写法：`addAnimationByIndices(tag, name, prefix, indices, framerate)`**。

### luaSpritePlayAnimation(tag:String, name:String, forced:Bool = false)

播放 Lua 精灵的动画。

返回：无返回。**替代写法：`playAnim(tag, name, forced)`**。

### setLuaSpriteCamera(tag:String, camera:String = '')

让 Lua 精灵只由某台相机渲染。

返回：`Bool`，找到精灵 `true`。**替代写法：`setObjectCamera(tag, camera)`**。

### setLuaSpriteScrollFactor(tag:String, scrollX:Float, scrollY:Float)

设置 Lua 精灵的滚动视差。

返回：`Bool`，找到精灵 `true`。**替代写法：`setScrollFactor(tag, scrollX, scrollY)`**。

### scaleLuaSprite(tag:String, x:Float, y:Float)

缩放 Lua 精灵并刷新碰撞箱。

返回：`Bool`，找到精灵 `true`。**替代写法：`scaleObject(tag, x, y, true)`**。

### getPropertyLuaSprite(tag:String, variable:String)

读 Lua 精灵的属性，`variable` 支持点号路径。

返回：属性值；tag 不存在返回 `null`。**替代写法：`getProperty(tag + '.' + variable)`**。

### setPropertyLuaSprite(tag:String, variable:String, value:Dynamic)

写 Lua 精灵的属性。

返回：`Bool`，成功 `true`。**替代写法：`setProperty(tag + '.' + variable, value)`**。

### musicFadeIn(duration:Float, fromValue:Float = 0, toValue:Float = 1)

当前音乐的淡入。

返回：无返回。**替代写法：`soundFadeIn('', duration, fromValue, toValue)`**。

### musicFadeOut(duration:Float, toValue:Float = 0)

当前音乐的淡出。

返回：无返回。**替代写法：`soundFadeOut('', duration, toValue)`**。

> 源码里还有四处被 `/* */` 整段注释掉的注册，**运行时根本不存在**，不要调用：`getGlobals`、`getPropertyAdvanced`、`setPropertyAdvanced`、`makeLuaGifSprite`。
