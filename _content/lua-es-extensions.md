# Parker 扩展：Engine Custom ES Lua 方言

<!-- source: psych/script/ESCompat.hx -->

「Engine Custom ES」是 Parker Engine 在 Psych 原版 Lua API 之上额外提供的一层方言兼容，实现在 `source/psych/script/ESCompat.hx`。本页收录它注册的**全部 67 个函数**与配套全局变量，每个都标注为 **Parker 扩展**。

## 这一层是怎么接进引擎的

- **注册时机**：`ESCompat.register(this)` 在 `FunkinLua` 构造函数**末尾**调用，此时 Psych 原版的那 232 个函数已经全部注册完毕（只有菜单专用的 `camFollowPos` / `camFollow` 排在它之后注册）。
- **不覆盖 Psych 回调**：ES 只做**新增**。源码注释写明「it only adds callbacks, so scripts written for Psych keep behaving exactly as before」——凡是 Psych 已有的能力（`setProperty`、`doTween*` 等），ES 不会重新注册，只是给一个更短的别名去复用原函数。少数「会改到 Psych 函数行为」的地方都在下文《与 Psych 函数重叠的地方要留意》里单独列出：`setHealthBarColors` 的三参数重载、`setTextBorder` 的参数顺序自动交换、`makeLuaSprite` 的图集自动识别，以及菜单态把 `setObjectCamera` 置 `nil`。
- **全局常量**：桌面上会额外写入两个只读全局 `monitorWidth`、`monitorHeight`（显示器分辨率）；另外注册了 31 个缓动名各两种大小写共 **62 个全局变量**（`quadOut` 与 `QuadOut` 都等于字符串 `'quadOut'`），这样 ES 脚本可以写 `doTweenY('t', 'obj', 0, 1, QuadOut)` 而不用加引号——不注册的话这个标识符是 `nil`，补间会静默退化成 `linear`。已注册的名字是：`linear`、`quadIn/Out/InOut`、`quartIn/Out/InOut`、`quintIn/Out/InOut`、`sineIn/Out/InOut`、`expoIn/Out/InOut`、`circIn/Out/InOut`、`cubeIn/Out/InOut`、`backIn/Out/InOut`、`elasticIn/Out/InOut`、`bounceIn/Out/InOut`。
- **`lerp(a, b, t)`**：每个 Lua 脚本各有独立的 Lua 状态与 `this`，另一个脚本里定义的全局 `lerp()` 在这里是 `nil`，所以引擎自己提供了一个。
- **警告而不是崩溃**：ES 函数在参数缺失或找不到对象时走 `warn()`，即调用 `luaTrace(..., FlxColor.RED)`，是否显示取决于该脚本的 `luaDebugMode`。

## 菜单态（LuaSState）下的行为差异

当脚本由 `states/<名字>.lua` 这类**自定义菜单状态**（`LuaSState`）启动时（`FunkinLua.menuMode == true`），没有 `PlayState.instance` 可以挂对象，于是脚本改用自己的一套注册表：

| 注册表 | 作用 |
| --- | --- |
| `menuSprites` / `menuTexts` | 该脚本的 Lua 精灵与文本 |
| `menuTweens` / `menuTimers` | 该脚本的补间与计时器 |
| `menuSounds` | 该脚本的音效 |
| `menuVariables`（静态） | 菜单脚本共用的变量表，最后一个菜单脚本停掉时清空 |

具体影响：

- `add()` / `addLuaSprite()` 在菜单态是**直接 append**，不认 `front` 参数——创建顺序就是绘制顺序；`menuBackIndex` 用来记录「往后插」的位置。
- `setOrder()` 则按 `FlxState.members` 的下标插入，可以精确控制层级。
- 菜单态**相机布局**由 `LuaSState.create()` 决定：`camGame` 被滚动半屏（`scroll` 设为 `-width/2, -height/2`），所以 Lua 坐标是**屏幕中心为原点**；同时新建一台不滚动的 `camHUD` 供 `setCam('camHUD')` 使用。`camFollowPos()` / `camFollow()` 就是用来在这个滚动坐标系里「跟随」某个内容点的。
- 菜单态**没有** `setObjectCamera`：源码在 `menuMode` 下显式把它设为 `nil`（`Lua.gpushnil`），因为 ES 脚本会用 `if setObjectCamera then` 探测它。**`setCam()` 才是菜单态的相机设置入口。**
- 角色、视频、轨迹、血条、strum 相关函数都要求有 `PlayState`，菜单态会红字警告并直接返回。
- 菜单脚本的 `onCreate()` 由 `LuaSState.create()` 统一调用，只调一次，且在相机布局就位之后；游戏脚本则由 `FunkinLua` 构造函数末尾调用。

## 两个特殊回调

- **`onPlayAnim(tag, anim)`**（Parker 扩展）：ES 的「角色切换动画」回调。它不是引擎原生派发的，而是 `ESCompat.tick()` 在**每次派发本脚本的 `onUpdate` 之前**检查 `boyfriend`、`dad`、`gf` 以及所有 `makeChar()` 创建的角色，一旦发现 `animation.curAnim.name` 与上一次不同就派发一次。`tag` 是角色标识（内置三个角色用 `'boyfriend'` / `'dad'` / `'gf'`，`makeChar` 的用其 tag）。
- **`onTyping(tag)`**（Parker 扩展）：打字机文本（`setTextSpeed()` + `setText()`）每显示出一个字符时派发，`tag` 是该文本的 tag。

## API 参考

### 别名与通用操作

<!-- source: psych/script/ESCompat.hx -->

**Parker 扩展**，共 16 个。

### set(variable:String, value:Dynamic)

**Parker 扩展。** `setProperty` 的短别名，写属性时可容忍失败。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `variable` | `String` | 属性路径，支持 `'spr.x'`；写不进去时会退化成脚本变量 |
| `value` | `Dynamic` | 值 |

返回：`Bool`，恒为 `true`（缺参数时 `false` 并警告）。

### get(variable:String):Dynamic

**Parker 扩展。** `getProperty` 的短别名。

返回：属性值；路径不存在返回 `null`。

### add(tag:String, ?front:Bool = false)

**Parker 扩展。** 把精灵/文本/其它 `FlxBasic` 加进场景，等价于 `addLuaSprite` + `addLuaText` 的统一入口，也接受用变量存放的对象。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 对象 tag |
| `front` | `Bool` | 加到最前；菜单态忽略此项 |

返回：无返回。

### remove(tag:String)

**Parker 扩展。** 从场景移除并销毁对象，同时清理它在该脚本的精灵/文本/变量/轨迹/视频/血条注册表里的条目。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 对象 tag |

返回：无返回。

### scale(tag:String, x:Float, y:Float, ?updateHitbox:Bool = true)

**Parker 扩展。** 设置缩放。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 精灵 tag |
| `x` / `y` | `Float` | 缩放倍率 |
| `updateHitbox` | `Bool` | 是否刷新碰撞箱，默认 `true` |

返回：无返回。

### addAnim(tag:String, name:String, prefix:String, ?framerate:Int = 24, ?loop:Bool = true)

**Parker 扩展。** 按前缀加动画；对象当前没有动画时会立刻播放这个新动画。

返回：无返回。

### setCam(tag:String, camera:String = '')

**Parker 扩展。** 设置对象由哪台相机渲染。**菜单态下这是唯一可用的相机设置入口**（菜单里 `setObjectCamera` 是 `nil`）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 精灵 tag |
| `camera` | `String` | `'camHUD'` / `'hud'`（菜单的原始相机或 `PlayState.camHUD`）、`'camOther'` / `'other'`、`'camVideo'` / `'video'`，其他值（含默认空串）为 `camGame` |

返回：`Bool`，找到精灵 `true`。

### setOrder(tag:String, position:Int)

**Parker 扩展。** 按 `FlxState.members` 下标重排对象层级（会 clamp 到合法范围）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 对象 tag |
| `position` | `Int` | 目标下标 |

返回：无返回。

### getOrder(tag:String):Int

**Parker 扩展。** 读取对象在场景成员里的下标。

返回：`Int`；未找到返回 `-1`。

### setVelocity(tag:String, x:Float, y:Float)

**Parker 扩展。** 直接设置精灵速度。

返回：无返回。

### doTweenScale(tag:String, obj:String, x:Float, y:Float, duration:Float, ?ease:String)

**Parker 扩展。** 缩放补间，且在补间过程中**保持视觉中心不变**（每次更新按宽高变化量补回 `x`/`y`，这是 Psych 的 `scaleObject` 做不到的）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 补间 tag，同名会先取消 |
| `obj` | `String` | 目标对象路径 |
| `x` / `y` | `Float` | 目标缩放 |
| `duration` | `Float` | 时长（秒） |
| `ease` | `String` | 缓动名，默认 `linear` |

返回：无返回。完成时触发 `onTweenCompleted(tag)`。

### setArray(properties:Dynamic, values:Dynamic)

**Parker 扩展。** 批量设置属性。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `properties` | `Table` | 属性名数组 |
| `values` | `Table` | 值数组；**长度与 `properties` 不同时**，所有属性都写第一个值（广播模式） |

返回：无返回。

### addArray(tags:Dynamic, ?front:Bool = false)

**Parker 扩展。** 批量 `add()`。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tags` | `Table` | tag 数组 |
| `front` | `Bool` | 是否加到最前 |

返回：无返回。

### getAnimName(tag:String):String

**Parker 扩展。** 读取精灵当前动画名。

返回：`String`；精灵不存在或没有当前动画时返回 `''`。

### scroll(tag:String, scrollX:Float, scrollY:Float)

**Parker 扩展。** `setScrollFactor` 的短别名。返回：无返回。

### lerp(a:Float, b:Float, t:Float):Float

**Parker 扩展。** 线性插值工具（因为每个脚本是独立 Lua 状态，别的脚本定义的 `lerp` 在这里取不到）。

返回：`Float`，`a` 到 `b` 按 `t` 插值的结果。

### 对象创建

<!-- source: psych/script/ESCompat.hx -->

**Parker 扩展**，共 16 个。这一组创建的多数是**非精灵对象**（角色、背景、视频、轨迹、血条），它们存在变量表里而不是精灵注册表里，因此 `addLuaSprite` 不管它们，要用 `add()` / `setOrder()` 排层级。

### ColorBox(tag:String, color:String, x:Float = 0, y:Float = 0, width:Float = 0, height:Float = 0)

**Parker 扩展。** 创建一个纯色矩形（`makeColorBox` 的同体别名，但参数顺序按 `color` 在前）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | tag |
| `color` | `String` | 颜色，可带 `#` 或 `0x` |
| `x` / `y` | `Float` | 位置 |
| `width` / `height` | `Float` | 尺寸；**`<= 1` 时按整屏处理**（`FlxG.width` / `FlxG.height`），这是 ES 脚本用 `0` 或 `1` 表示「铺满」的约定 |

返回：无返回。菜单态且尺寸用了占位值时会把 `scrollFactor` 设为 `(0, 0)`，避免半屏滚动的菜单相机露出边缘。

### makeColorBox(tag:String, x:Float = 0, y:Float = 0, width:Float = 0, height:Float = 0, color:String = '000000')

**Parker 扩展。** 同上，但参数顺序是 ES 的 `(tag, x, y, width, height, color)`。

返回：无返回。

### BGSprite(tag:String, image:String, x:Float = 0, y:Float = 0, ?scrollX:Float = 1, ?scrollY:Float = 1)

**Parker 扩展。** 创建引擎的 `BGSprite`（带 idle 动画能力的背景精灵）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `image` | `String` | 图片名（走 `Paths.image`） |
| `scrollX` / `scrollY` | `Float` | 视差系数，默认 `1` |

返回：无返回。菜单态会强制 `scrollFactor = (0, 0)`，让它当屏幕空间装饰而不是被半屏滚动推走。

### FlxBackdrop(tag:String, image:String, x:Float = 0, y:Float = 0, ?axis:String = 'X')

**Parker 扩展。** 创建无限平铺背景。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `axis` | `String` | `'X'`（默认）、`'Y'`，其他值为 `XY` 双向平铺 |

返回：无返回。菜单态同样会清零 `scrollFactor`。

### makeChar(tag:String, character:String, x:Float = 0, y:Float = 0, ?isPlayer:Bool = false)

**Parker 扩展。** 在歌曲里创建一个额外的角色（`Character`），并登记到 ES 的角色表，因此它的动画切换会产生 `onPlayAnim(tag, anim)` 回调。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 角色 tag |
| `character` | `String` | 角色名（`characters/<名字>.json`） |
| `x` / `y` | `Float` | 位置 |
| `isPlayer` | `Bool` | 是否按玩家侧角色处理（朝向等） |

返回：无返回。**仅歌曲中可用**，菜单态会警告。

### setLongSing(characters:String, value:Bool = true)

**Parker 扩展。** 让角色的 sing 动画「永不结束」（`singDuration` 设为 9999），用于做长音。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `characters` | `String` | 角色名，**逗号分隔**可以一次传多个；支持 `dad` / `opponent`、`boyfriend` / `bf` / `player`、`gf` / `girlfriend`，也可以是 `makeChar` 的 tag |
| `value` | `Bool` | `true` 开启长音；`false` 恢复原始 `singDuration`（第一次调用时会记录原值，取不到时回退为 `4`） |

返回：无返回。

### MoveCamOnAnim(charIdx:Int, anim:String, x:Float = 0, y:Float = 0)

**Parker 扩展。** 登记「角色 X 播某动画时相机偏移多少」，并在动画正在播放时立即应用。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `charIdx` | `Int` | **ES 的角色序号：`0` = 对手（dad）、`1` = 玩家（boyfriend）、`2` = 女友（gf）** |
| `anim` | `String` | 动画名 |
| `x` / `y` | `Float` | 相机目标点偏移 |

返回：无返回。规则保存在 `ESState.camRules` 里，每帧由 `ESCompat.tick()` 按角色当前动画重新应用；若引擎自己重新定位了 `camFollow`，引擎会检测到并把旧偏移清零（`applyCamOffset()`）。

### makeHealthBar(tag:String, x:Float = 0, y:Float = 0)

**Parker 扩展。** 创建一条额外的血条。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 血条 tag；**名字里含 `dad` 或 `opponent` 时渲染成从右往左**，否则从左往右 |
| `x` / `y` | `Float` | 相对引擎自带血条的偏移（宽高也照抄引擎血条，取不到时回退 `600x20`） |

返回：无返回。**仅歌曲中可用。** 颜色用 `setHealthBarColors(barTag, leftHex, rightHex)` 改（见下文说明）。

### makeVideoSprite(tag:String, path:String, x:Float = 0, y:Float = 0, ?width:Float = 0, ?height:Float = 0, ?options:String = null)

**Parker 扩展。** 创建一个可通过 tag 控制的视频精灵（比 Psych 的 `makeLuaVideoSprite` 多了尺寸与选项）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 视频 tag |
| `path` | `String` | 视频名（`videos/` 下的 mp4） |
| `x` / `y` | `Float` | 位置 |
| `width` / `height` | `Float` | 尺寸；**两者都大于 0** 时才在 `onFormat` 回调里缩放 |
| `options` | `String` | 传 `'looping'`（大小写不敏感）会自动换成引擎的循环常量 |

返回：无返回。加载失败会警告并销毁。**仅歌曲中可用**，且需要 `VIDEOS_ALLOWED`。

### videoPlay(tag:String)

**Parker 扩展。** 播放 `makeVideoSprite` 创建的视频。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 视频 tag |

返回：无返回（找不到 tag 会警告）。

### makeTrailSpirit(tag:String, target:String, ?color:String = 'FFFFFF')

**Parker 扩展。** 给某个精灵加拖尾（内部是 `FlxTrail`，初始参数为 10 帧长度 / 3 帧分隔 / 0.2 透明度 / 0.05 渐变）。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 拖尾 tag，之后用 `trailXxx` 系列调节 |
| `target` | `String` | 被跟随的精灵 tag |
| `color` | `String` | 颜色参数，**当前实现未使用**（保留以兼容 ES 调用） |

返回：无返回。**仅歌曲中可用**；被跟随的精灵必须已存在。

### trailDirection(tag:String, direction:String)

**Parker 扩展。** 设置拖尾方向。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 拖尾 tag |
| `direction` | `String` | `'x'` 只横向、`'y'` 只纵向、`'none'` / `'static'` 静止、其他值（含 `'follow'`）双轴跟随 |

返回：无返回。

### trailSpeed(tag:String, speed:Float)

**Parker 扩展。** 调整拖尾的采样疏密（源码直接改 `FlxTrail._difference`，取值 `speed / 1000`，下限 `0.001`）。数值越小拖尾越「厚」。

返回：无返回。

### trailDelay(tag:String, delay:Float)

**Parker 扩展。** 设置帧间隔（秒），内部换算成帧数（`delay * 60`，最少 1 帧）。

返回：无返回。

### trailAlpha(tag:String, alpha:Float)

**Parker 扩展。** 设置拖尾起始透明度（`FlxTrail._transp`）。

返回：无返回。

### trailLife(tag:String, life:Float)

**Parker 扩展。** 设置拖尾存活时长（秒），按当前帧间隔换算成需要多少节拖尾并调整长度。

返回：无返回。

### Shader 与变量数组

<!-- source: psych/script/ESCompat.hx -->

**Parker 扩展**，共 4 个。**注意这里和 Psych 的差异**：Psych 的 `setSpriteShader`/`setShaderFloat` 系列是按**挂着色器的对象**操作的；ES 的 `makeShader()` 先给着色器一个**自己的 tag**，再 `setCameraShader()` 把它挂到相机上，`setShaderFloat(tag, ...)` 也能直接按这个 tag 找到着色器（`FunkinLua.getShader()` 找不到对象时会回落到 `ESCompat.getShader()`）。

### makeShader(tag:String, name:String):Bool

**Parker 扩展。** 加载 `shaders/<name>.frag` + `.vert`，并以 `tag` 登记。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 着色器 tag |
| `name` | `String` | 着色器文件名（不带扩展名） |

返回：`Bool`，成功 `true`。`ClientPrefs.shaders` 关闭时返回 `false`；文件缺失时警告并返回 `false`。加载成功后同一份源码也会写进 `PlayState.runtimeShaders`，于是 Psych 的 `setSpriteShader(obj, name)` 也能直接用它。

### setCameraShader(camera:String, shaders:Dynamic):Bool

**Parker 扩展。** 把若干已加载的着色器作为滤镜挂到某台相机上。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `camera` | `String` | 相机名（`'camGame'` / `'camHUD'` / `'camOther'` / `'camVideo'`） |
| `shaders` | `Table` | 一个或多个 `makeShader` 的 tag；未找到的会被跳过并警告 |

返回：`Bool`，成功 `true`。每次调用都会**整体替换**该相机的滤镜列表。

### doTweenFloatArray(tag:String, names:Dynamic, values:Dynamic, duration:Float, ?ease:String)

**Parker 扩展。** 同时补间多个**脚本变量**的数值。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 补间 tag |
| `names` | `Table` | 变量名数组 |
| `values` | `Table` | 目标值数组；长度不匹配但只有一个值时，全部用这一个值 |
| `duration` | `Float` | 时长（秒） |
| `ease` | `String` | 缓动名 |

返回：无返回。起始值取变量表里的当前值；完成后触发 `onTweenCompleted(tag)`。

### setVarArray(names:Dynamic, values:Dynamic)

**Parker 扩展。** 批量写脚本变量。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `names` | `Table` | 变量名数组 |
| `values` | `Table` | 值数组；长度不匹配时广播第一个值 |

返回：无返回。除了写进变量表，还会 `set()` 成该脚本的 Lua 全局，让同名变量在脚本里可直接读。

### 文本与打字机

<!-- source: psych/script/ESCompat.hx -->

**Parker 扩展**，共 4 个。

### setText(tag:String, text:String):Bool

**Parker 扩展。** 设置文本内容。**如果这个 tag 用 `setTextSpeed()` 设过正的速度，且新内容长度大于 1，就会自动播放打字机效果**，每显示一个字符触发一次 `onTyping(tag)`。

返回：`Bool`，找到文本 `true`。

### setTextAlign(tag:String, alignment:String = 'left'):Bool

**Parker 扩展。** 设置对齐（`'right'` / `'center'`，其他为左对齐）。

返回：`Bool`。

### setTextSpeed(tag:String, speed:Float)

**Parker 扩展。** 设置打字机速度。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 文本 tag |
| `speed` | `Float` | 每个字符的间隔秒数；**`<= 0` 表示关闭打字机**并停掉正在跑的计时器 |

返回：无返回。

### setTextGradient(tag:String, color1:String, color2:String = null, angle:Float = 0)

**Parker 扩展。** 渐变文字。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `tag` | `String` | 文本 tag |
| `color1` | `String` | 顶部/主色 |
| `color2` | `String` | 第二个颜色，**当前实现未使用** |
| `angle` | `Float` | 角度，**当前实现未使用** |

返回：无返回。源码注释写明 `FlxText` 没有渐变支持，所以这里只是把 `color1` 当纯色用，属于「有接口但不完整」的实现，别指望真的渐变。

### 音符与 strum

<!-- source: psych/script/ESCompat.hx -->

**Parker 扩展**，共 8 个。全部**只在歌曲中可用**，菜单态会警告「Strums only exist while a song is playing!」。

### setNoteY(note:Int, y:Float)

**Parker 扩展。** 设置第 `note` 个 strum 的 Y。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `note` | `Int` | strum 下标；负数取 0，超长按长度取模 |

返回：无返回。

### setNoteAngle(note:Int, angle:Float)

**Parker 扩展。** 设置第 `note` 个 strum 的角度。返回：无返回。

### setStrumY(group:String, y:Float)

**Parker 扩展。** 设置整组 strum 的 Y。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `group` | `String` | `'player'` / `'bf'` / `'boyfriend'`、`'opponent'` / `'dad'` / `'enemy'`，其他值（含 `nil`）为全部 strum |

返回：无返回。

### setStrumPos(group:String, x:Float, y:Float)

**Parker 扩展。** 同组一起 `setPosition`。`group` 规则同上。返回：无返回。

### setStrumAlpha(group:String, alpha:Float)

**Parker 扩展。** 同组一起设透明度。`group` 规则同上。返回：无返回。

### strumTweenX(tag:String, group:String, x:Float, duration:Float, ?ease:String)

**Parker 扩展。** 整组 strum 的 X 补间（一组的每个 strum 各建一条补间，只把第一条登记到 tag 下供 `cancelTween` 取消）。

返回：无返回。完成后触发 `onTweenCompleted(tag)`。

### strumTweenAlpha(tag:String, group:String, alpha:Float, duration:Float, ?ease:String)

**Parker 扩展。** 整组 strum 的透明度补间。返回：无返回。

### stepEvent(stepOrTable:Dynamic, ?func:Dynamic)

**Parker 扩展。** 在指定步数触发一个 Lua 函数。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `stepOrTable` | `Table` 或 `Int` | 一个步数，或步数数组 |
| `func` | `Function` | 要调用的 Lua 函数（无参） |

返回：无返回。引擎依赖 `onEventSet(curStep)` 记录的 `lastEventSetStep` 判断是否到达；每个步数只触发一次（记在 `firedSteps` 里）；本轮没触发成功时函数引用会被释放，避免堆积。

### 菜单与 Freeplay

<!-- source: psych/script/ESCompat.hx -->

**Parker 扩展**，共 10 个。主要用于 `states/<名字>.lua` 这类自定义菜单状态脚本。

### switchLuaMenu(name:String):Bool

**Parker 扩展。** 切换到另一个 Lua 菜单状态。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 状态名（可带 `.lua`，会被去掉）；实际去加载 `states/<名字>.lua` |

返回：`Bool`，成功 `true`。

### switchSourceMenu(name:String):Bool

**Parker 扩展。** 切换到引擎内置状态，按顺序在 `options.`、`states.menu.`、`states.`、`substates.`、`substates.game.`、无包名 这 6 个前缀里查找类。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `name` | `String` | 类名，如 `'FreeplayState'` |

返回：`Bool`，成功 `true`；找不到或构造失败时警告并返回 `false`。会走 `MusicBeatState.switchState()`，保留引擎转场。

### playMenuMusic(name:String, ?volume:Float = 1, ?loop:Bool = true)

**Parker 扩展。** 菜单里播放音乐（`Paths.music` + `FlxG.sound.playMusic`）。

返回：无返回。

### preloadSound(name:String)

**Parker 扩展。** 预加载一个音效（内部只调 `Paths.sound(name)` 触发加载）。

返回：无返回。

### getFreeplaySongCount():Int

**Parker 扩展。** 可玩歌曲总数。数据来源见下。

返回：`Int`。

### getFreeplaySongName(index:Int):String

**Parker 扩展。** 第 `index` 首歌的歌曲名（用于谱面文件路径）。

返回：`String`；下标越界返回 `null`。

### getFreeplaySongDisplay(index:Int):String

**Parker 扩展。** 第 `index` 首歌的显示名。Psych 歌曲没有单独的显示名，所以**当前实现返回与 `getFreeplaySongName` 相同的值**。

返回：`String` 或 `null`。

### getFreeplayDiffCount(index:Int):Int

**Parker 扩展。** 第 `index` 首歌的难度个数。

返回：`Int`；歌曲不存在返回 `0`。

### getFreeplayDiffName(index:Int, difficulty:Int):String

**Parker 扩展。** 第 `index` 首歌第 `difficulty` 个难度的名字（越界会自动 clamp 到首/末位）。

返回：`String` 或 `null`。

### startFreeplaySongIndex(index:Int, ?difficulty:Int = 0):Bool

**Parker 扩展。** 直接开始第 `index` 首歌。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `index` | `Int` | 歌曲下标 |
| `difficulty` | `Int` | 难度下标，默认 `0`，越界会 clamp |

返回：`Bool`，成功 `true`。会设置 `Paths.currentModDirectory`、`PlayState.storyWeek`、`PlayState.SONG`，然后走 `LoadingState.loadAndSwitchState(new PlayState())`。谱面文件找不到时警告并返回 `false`。

> **Freeplay 列表的来源**：当前 mod 有 `weeks/` 目录时，只读该 mod 自己的 week JSON（尊重 `songList.txt` / `weekList.txt`、`hideFreeplay`、`startUnlocked`、`weekBefore` 的解锁判定）；否则回落到 `WeekData` 的全部 week。结果会缓存在静态变量里，同一进程内只算一次。

### 窗口助手

<!-- source: psych/script/ESCompat.hx -->

**Parker 扩展**，共 9 个。除 `isFullscreen` / `setWindowScale` / 边框相关在 `sys` 平台可用外，透明窗口与任务栏两项需要 **Windows 桌面（`cpp && windows`）** 构建，其余平台只会警告。

### isFullscreen(?value:Bool):Bool

**Parker 扩展。** 查询/设置全屏。

| 参数 | 类型 | 说明 |
| --- | --- | --- |
| `value` | `Bool` | 传了值就设置；不传只查询 |

返回：`Bool` 当前全屏状态；非 `sys` 平台恒为 `false`。

### setWindowScale(width:Float, ?height:Float = 0)

**Parker 扩展。** 调整窗口大小。`height <= 0` 时按 16:9 由宽度推算；算出小于 1 的尺寸会警告并放弃。

返回：无返回。

### doBorderless()

**Parker 扩展。** 去掉窗口边框。返回：无返回。

### removeBorderless()

**Parker 扩展。** 恢复窗口边框。返回：无返回。

### doTransWindow()

**Parker 扩展。** 开启分层透明窗口（黑色为透明色），**仅 Windows 桌面**，其他平台警告并忽略。

返回：无返回。

### removeTransWindow()

**Parker 扩展。** 关闭透明窗口，**仅 Windows 桌面**。返回：无返回。

### HideTaskBar()

**Parker 扩展。** 隐藏任务栏，**仅 Windows 桌面**。返回：无返回。

### RestoreTaskBar()

**Parker 扩展。** 恢复任务栏，**仅 Windows 桌面**。返回：无返回。

### SystemClose()

**Parker 扩展。** 直接 `Sys.exit(0)` 退出游戏（`sys` 平台；其他平台警告）。

返回：无返回。

## Parker 相对 Psych 的增量亮点

1. **更短的属性/对象别名**：`set` / `get` / `add` / `remove` / `scale` / `scroll` / `setCam` / `setOrder` / `addAnim` / `addArray` / `setArray`，把 Psych 那套长名字 API 压成 ES 脚本常见的一行式写法。
2. **着色器按 tag 管理**：`makeShader(tag, name)` + `setCameraShader(camera, {tags})`，着色器不再必须挂在精灵上，可以直接当相机滤镜；并且与 Psych 的 `setSpriteShader` 互通。
3. **菜单脚本体系**：`switchLuaMenu` / `switchSourceMenu` / `playMenuMusic` / `getFreeplay*` / `startFreeplaySongIndex` 让 `.lua` 能整段替换菜单，配合 `LuaSState` 的「半屏滚动 camGame + 原始 camHUD」相机布局与菜单专用注册表。
4. **角色/视觉表现扩展**：`makeChar`、`setLongSing`、`MoveCamOnAnim`、`makeHealthBar`、`makeTrailSpirit` + 5 个 `trail*` 调节、`BGSprite` / `FlxBackdrop` / `ColorBox`，以及数字数组补间 `doTweenFloatArray`、保持视觉中心的 `doTweenScale`。
5. **打字机文本与窗口控制**：`setTextSpeed` / `setText` / `onTyping` 提供逐字显示；`isFullscreen` / `setWindowScale` / `doBorderless` / `doTransWindow` / `HideTaskBar` / `SystemClose` 提供桌面窗口级控制。
6. **步数事件**：`stepEvent({steps}, func)` + `onEventSet(curStep)` 让脚本自己排「第 N 步做什么」，不必写一堆 `if curStep == n`。

## 与 Psych 函数重叠的地方要留意

- **`setTextBorder` 的参数顺序在做兼容**：ES 写 `setTextBorder(tag, color, size)`，Psych 写 `setTextBorder(tag, size, color)`。`FunkinLua` 里的实现会检测「`size` 是字符串而 `color` 不是」并自动交换，两种写法都能用。
- **`setHealthBarColors` 有三个参数的重载**：`setHealthBarColors(barTag, leftHex, rightHex)` 会转交给 `ESCompat.setHealthBarColors()`，作用于 `makeHealthBar()` 建的血条；只传两个参数时仍然是 Psych 原版行为（改引擎自带血条）。血条不存在时警告。
- **`makeLuaSprite` 被扩了行为**：`images/<image>.xml` 存在时会自动按 Sparrow 图集加载；菜单态下可选的第 5、6 个参数是 `scrollFactor`。
- **菜单态 `setObjectCamera` 是 `nil`**，用 `setCam()`；这是刻意的，源码里显式 `pushnil` 了它。
