import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

ApplicationWindow {
    id: win
    width: 340
    height: 720
    visible: true
    title: "美的空调"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
           | Qt.NoDropShadowWindowHint
    color: "transparent"
    background: null

    readonly property color cCard: "#FFFFFF"
    readonly property color cText: "#1A1C1E"
    readonly property color cSub: "#9AA0A6"
    readonly property color cDim: "#C3C8CD"
    readonly property color cBlue: "#01A4F3"
    readonly property color cTrack: "#E9EDF0"

    // 弹层状态: "" | "mode" | "fan"
    property string pickerType: ""

    property var modeOpts: [
        {k: "auto", n: "自动"}, {k: "cool", n: "制冷"}, {k: "dry", n: "除湿"},
        {k: "heat", n: "制热"}, {k: "fan_only", n: "送风"}
    ]

    FontLoader { id: harry; source: Qt.resolvedUrl("fonts/HarmonyOS_Sans_SC_Regular.ttf") }
    font.family: harry.name

    Component.onCompleted: bridge.debugLog("界面已加载 v8.2 win=" + win.width + "x" + win.height + " shell=" + shell.width + "x" + shell.height)

    Shortcut { sequence: "Esc"; onActivated: bridge.closePanel() }

    function snapTo(path) {
        shell.grabToImage(function(result) {
            console.log("SNAP save:", path, "->", result.saveToFile(path))
        })
    }

    // 圆角容器
    Rectangle {
        id: shell
        anchors.fill: parent
        radius: 24
        // 顶部浅蓝渐变, 与空调图的背景无缝衔接
        gradient: Gradient {
            GradientStop { position: 0.0; color: "#DEEFF7" }
            GradientStop { position: 0.12; color: "#DDEFF7" }
            GradientStop { position: 0.32; color: "#E1EFF8" }
            GradientStop { position: 0.55; color: "#E8F3F9" }
            GradientStop { position: 0.80; color: "#EFF6FA" }
            GradientStop { position: 1.00; color: "#F5F6F8" }
        }
        border.color: "#E4E7EB"
        border.width: 1

        // ---------- 标题栏 ----------
        Item {
            id: header
            x: 0; y: 0
            z: 2
            width: parent.width; height: 58
            Rectangle { anchors.fill: parent; color: "#DEEFF7" }

            // 电源开关: 开机红色 / 关机黑色, 始终清晰(不参与整页置灰)
            Canvas {
                width: 26; height: 26
                anchors.left: parent.left; anchors.leftMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                property bool lit: bridge.state.power
                onLitChanged: requestPaint()
                onPaint: {
                    var c = getContext("2d")
                    c.reset()
                    var s = 26 / 24
                    c.strokeStyle = lit ? "#F5544E" : "#34C759"
                    c.lineWidth = 2.4 * s
                    c.lineCap = "round"
                    c.beginPath()
                    c.moveTo(12 * s, 3.2 * s)
                    c.lineTo(12 * s, 10.8 * s)
                    c.stroke()
                    c.beginPath()
                    c.arc(12 * s, 11.92 * s, 7.3 * s, -2.365, -0.777, true)
                    c.stroke()
                }
                MouseArea {
                    anchors.fill: parent; anchors.margins: -10
                    cursorShape: Qt.PointingHandCursor
                    onClicked: bridge.togglePower()
                }
            }
            Text {
                anchors.centerIn: parent
                text: "壁挂式空调"
                font.pixelSize: 17
                font.weight: Font.DemiBold
                color: cText
                opacity: bridge.state.power ? 1 : 0.3
            }
            // 关闭(右)
            Canvas {
                width: 18; height: 18
                anchors.right: parent.right
                anchors.rightMargin: 18
                anchors.verticalCenter: parent.verticalCenter
                opacity: bridge.state.power ? 1 : 0.3
                onPaint: {
                    var c = getContext("2d")
                    c.reset()
                    c.strokeStyle = "#1A1C1E"
                    c.lineWidth = 2.4
                    c.lineCap = "round"
                    c.beginPath(); c.moveTo(3, 3); c.lineTo(15, 15); c.stroke()
                    c.beginPath(); c.moveTo(15, 3); c.lineTo(3, 15); c.stroke()
                }
                MouseArea { anchors.fill: parent; anchors.margins: -10
                            cursorShape: Qt.PointingHandCursor
                            onClicked: bridge.closePanel() }
            }
        }

        // ---------- 可滚动内容 ----------
        Flickable {
            id: flick
            objectName: "flick"
            y: header.height
            width: parent.width
            // 只留一点点给底部圆角
            height: parent.height - header.height - 10
            contentWidth: width
            contentHeight: contentCol.height + 16
            clip: true
            boundsBehavior: Flickable.StopAtBounds
            // 关机置灰: 对齐美居「禁用态统一 30%」的做法
            // 关机置灰: 对齐美居「禁用态统一 30%」的做法
            opacity: bridge.state.power ? 1 : 0.3
            Behavior on opacity { NumberAnimation { duration: 160 } }


            Column {
                id: contentCol
                x: 16
                width: parent.width - 32
                spacing: 12

                // 空调图: 关机/开机两张美居原图, 开机带送风效果
                Item {
                    x: -16
                    width: parent.width + 32; height: 170
                    Image {
                        anchors.fill: parent
                        source: bridge.state.power
                                ? Qt.resolvedUrl("ac_on.png")
                                : Qt.resolvedUrl("ac_off.png")
                        fillMode: Image.PreserveAspectFit
                        mipmap: true
                    }
                }

                // 室外/室内温度
                Item {
                    width: parent.width; height: 48
                    Row {
                        anchors.centerIn: parent
                        spacing: 56
                        Column {
                            spacing: 2
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: bridge.state.outdoor + "°C"
                                font.pixelSize: 20; font.weight: Font.DemiBold
                                color: cText
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: "室外盘管"
                                font.pixelSize: 12; color: cSub
                            }
                        }
                        Column {
                            spacing: 2
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: bridge.state.indoor + "°C"
                                font.pixelSize: 20; font.weight: Font.DemiBold
                                color: cText
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                text: "室内温度"
                                font.pixelSize: 12; color: cSub
                            }
                        }
                    }
                }

                // 温度卡: 大温度 + -/+ + 滑条
                Rectangle {
                    width: parent.width; height: 150
                    radius: 20
                    color: cCard

                    Item {
                        id: tempRow
                        property real dragVal: -1   // 拖拽中的临时温度
                        x: 16; y: 12
                        width: parent.width - 32; height: 76

                        Rectangle {
                            id: minusBtn
                            width: 46; height: 46; radius: 23
                            anchors.left: parent.left
                            anchors.verticalCenter: parent.verticalCenter
                            color: "#F1F3F5"
                            Text { anchors.centerIn: parent; text: "−"
                                   font.pixelSize: 24; color: cText }
                            MouseArea { anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: bridge.stepTemp(-0.5) }
                        }
                        Column {
                            anchors.centerIn: parent
                            spacing: -4
                            Row {
                                anchors.horizontalCenter: parent.horizontalCenter
                                spacing: 2
                                Text {
                                    id: bigTemp
                                    text: tempRow.dragVal >= 0
                                          ? tempRow.dragVal.toFixed(1)
                                          : bridge.state.target.toFixed(1)
                                    font.pixelSize: 44; font.weight: Font.DemiBold
                                    color: cText
                                }
                                Text {
                                    anchors.baseline: bigTemp.baseline
                                    text: "°C"
                                    font.pixelSize: 16; color: cSub
                                }
                            }
                        }
                        Rectangle {
                            id: plusBtn
                            width: 46; height: 46; radius: 23
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            color: "#F1F3F5"
                            Text { anchors.centerIn: parent; text: "+"
                                   font.pixelSize: 24; color: cText }
                            MouseArea { anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: bridge.stepTemp(0.5) }
                        }
                    }

                    // 滑条
                    Item {
                        id: slider
                        objectName: "tempSlider"
                        x: 24; y: 102
                        width: parent.width - 48; height: 32

                        property real pressX: -1  // 拖拽中的滑块中心像素位

                        function valueAt(px) {
                            var lo = bridge.state.minTemp
                            var hi = bridge.state.maxTemp
                            var r = Math.max(0, Math.min(1, px / slider.width))
                            return Math.round((lo + r * (hi - lo)) * 2) / 2
                        }
                        property real knobX: {
                            if (pressX >= 0) return pressX - 10
                            var lo = bridge.state.minTemp, hi = bridge.state.maxTemp
                            var r = hi > lo ? (bridge.state.target - lo) / (hi - lo) : 0
                            return r * (slider.width - 20)
                        }

                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            width: parent.width; height: 26; radius: 13
                            color: cTrack
                        }
                        Rectangle {
                            anchors.verticalCenter: parent.verticalCenter
                            x: 0
                            width: Math.min(slider.width, slider.knobX + 23)
                            height: 26; radius: 13
                            color: cBlue
                        }
                        Rectangle {
                            width: 20; height: 20; radius: 10
                            anchors.verticalCenter: parent.verticalCenter
                            x: slider.knobX
                            color: "#FFFFFF"
                        }
                        MouseArea {
                            anchors.fill: parent
                            anchors.margins: -14
                            preventStealing: true
                            cursorShape: Qt.PointingHandCursor
                            onPressed: function(mouse) {
                                var px = Math.max(0, Math.min(slider.width,
                                                              mouseX - 14))
                                slider.pressX = px
                                tempRow.dragVal = slider.valueAt(px)
                            }
                            onPositionChanged: function(mouse) {
                                if (!pressed) return
                                var px = Math.max(0, Math.min(slider.width,
                                                              mouseX - 14))
                                slider.pressX = px
                                tempRow.dragVal = slider.valueAt(px)
                            }
                            onReleased: function(mouse) {
                                if (tempRow.dragVal >= 0)
                                    bridge.setTarget(tempRow.dragVal)
                                slider.pressX = -1
                                tempRow.dragVal = -1
                            }
                            onCanceled: { slider.pressX = -1; tempRow.dragVal = -1 }
                        }
                    }
                }

                // 模式 / 风速
                Row {
                    width: parent.width
                    spacing: 10
                    Repeater {
                        model: [{t: "模式", v: bridge.state.modeName, ic: "snow"},
                                {t: "风速", v: bridge.state.fanName, ic: "fan"}]
                        Rectangle {
                            width: (parent.width - 10) / 2
                            height: 84; radius: 18
                            color: cCard
                            Column {
                                x: 18
                                spacing: 3
                                anchors.verticalCenter: parent.verticalCenter
                                Text { text: modelData.t
                                       font.pixelSize: 15; color: "#323232" }
                                Text { text: modelData.v
                                       font.pixelSize: 11; color: "#999999" }
                            }
                            Image {
                                source: "icons/" + modelData.ic + ".png"
                                width: 30; height: 30
                                fillMode: Image.PreserveAspectFit
                                anchors.right: parent.right
                                anchors.rightMargin: 18
                                anchors.verticalCenter: parent.verticalCenter
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: "PointingHandCursor"
                                onClicked: pickerType =
                                    (modelData.t === "模式" ? "mode" : "fan")
                            }
                        }
                    }
                }

                // 常用功能 / 设备设置 / 今日用电 统一包在圆角面板里
                Rectangle {
                    width: parent.width
                    height: cardInner.height + 36
                    radius: 18
                    color: cCard

                    Column {
                        id: cardInner
                        x: 18; y: 18
                        width: parent.width - 36
                        spacing: 14

                // 常用功能
                Text {
                    text: "常用功能"
                    font.pixelSize: 15; font.weight: Font.DemiBold
                    color: cText
                    topPadding: 6
                }
                Grid {
                    width: 260
                    anchors.horizontalCenter: parent.horizontalCenter
                    columns: 4
                    spacing: 24
                    Repeater {
                        model: FEATURES
                        delegate: Item {
                            property bool on: {
                                var k = modelData.key
                                if (k === "swing_up") return bridge.state.feat.swingUp
                                if (k === "swing_side") return bridge.state.feat.swingSide
                                if (k === "wind_dir") return bridge.state.feat.windDir
                                if (k === "aux") return bridge.state.feat.aux
                                return bridge.state.feat[k] || false
                            }
                            property bool enabledChip:
                                modelData.grey ? false
                                : (modelData.key === "aux"
                                   ? bridge.state.feat.auxEnabled : true)
                            width: 47
                            height: 86
                            opacity: enabledChip ? 1 : 0.45

                            // 圆形底: 默认 #F2F2F2, 选中实心蓝 + 白图标
                            Rectangle {
                                id: chip
                                width: 47; height: 47; radius: 23.5
                                anchors.horizontalCenter: parent.horizontalCenter
                                y: 2
                                color: on ? cBlue : "#F2F2F2"

                                Image {
                                    anchors.centerIn: parent
                                    source: "icons/" + modelData.icon
                                            + (on ? "_on.png" : ".png")
                                    width: 26; height: 26
                                    fillMode: Image.PreserveAspectFit
                                }
                                // 子面板入口角标: 仅"出风方向"有, 选中时同色蓝, 平时浅灰
                                Canvas {
                                    visible: modelData.key === "wind_dir"
                                    property bool lit: on
                                    width: 10; height: 10
                                    x: chip.width - 9.6
                                    y: chip.height - 9.6
                                    onLitChanged: requestPaint()
                                    onPaint: {
                                        var c = getContext("2d")
                                        c.reset()
                                        c.beginPath()
                                        c.moveTo(10, 0)
                                        c.lineTo(10, 10)
                                        c.lineTo(0, 10)
                                        c.closePath()
                                        c.fillStyle = lit ? "#01A4F3" : "#C9CED4"
                                        c.fill()
                                    }
                                }
                            }
                            Text {
                                anchors.horizontalCenter: parent.horizontalCenter
                                y: 58
                                text: modelData.name
                                font.pixelSize: 12
                                color: "#000000"
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: enabledChip
                                             ? Qt.PointingHandCursor : Qt.Arrow
                                onClicked: if (enabledChip)
                                               bridge.toggleFeature(modelData.key)
                            }
                        }
                    }
                }

                    }
                }

                // 设备设置 卡片
                Rectangle {
                    width: parent.width
                    height: setInner.height + 36
                    radius: 18
                    color: cCard

                    Column {
                        id: setInner
                        x: 18; y: 18
                        width: parent.width - 36
                        spacing: 14

                // 设备设置
                Text {
                    text: "设备设置"
                    font.pixelSize: 15; font.weight: Font.DemiBold
                    color: cText
                    topPadding: 6
                }
                Grid {
                    id: settingsGrid
                    objectName: "settingsGrid"
                    width: 272
                    anchors.horizontalCenter: parent.horizontalCenter
                    columns: 2
                    spacing: 16
                    Repeater {
                        model: [
                            {k: "display", t: "屏显", en: true},
                            {k: "sound", t: "声音", en: true},
                            {k: "dry", t: "干燥防霉", en: true},
                            {k: "light", t: "智能光感", en: false}
                        ]
                        delegate: Rectangle {
                            property bool on: bridge.state.set[modelData.k] || false
                            width: 128
                            height: 56; radius: 16
                            color: cCard
                            opacity: modelData.en ? 1 : 0.45
                            Text {
                                x: 16
                                anchors.verticalCenter: parent.verticalCenter
                                text: modelData.t
                                font.pixelSize: 13
                                color: modelData.en
                                       ? (on ? cText : cSub) : cDim
                            }
                            // 开关
                            Item {
                                width: 38; height: 22
                                anchors.right: parent.right
                                anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                Rectangle {
                                    anchors.fill: parent; radius: 13
                                    color: on && modelData.en ? cBlue : "#E2E6EA"
                                    Behavior on color {
                                        ColorAnimation { duration: 120 }
                                    }
                                }
                                Rectangle {
                                    width: 18; height: 18; radius: 9
                                    anchors.verticalCenter: parent.verticalCenter
                                    x: on && modelData.en ? 18 : 2
                                    color: "#FFFFFF"
                                    Behavior on x { NumberAnimation { duration: 120 } }
                                }
                            }
                            // 整卡可点(原来只有右侧小开关能点)
                            MouseArea {
                                anchors.fill: parent
                                onPressed: bridge.debugLog("按下 " + modelData.k)
                                cursorShape: modelData.en
                                             ? Qt.PointingHandCursor : Qt.Arrow
                                onClicked: if (modelData.en)
                                               bridge.toggleSetting(modelData.k)
                            }
                        }
                    }
                }

                    }
                }

                // 今日用电(单行信息卡)
                Rectangle {
                    width: parent.width; height: 54; radius: 16
                    color: cCard
                    Image {
                        source: "icons/energy.svg"
                        width: 20; height: 20
                        x: 16; anchors.verticalCenter: parent.verticalCenter
                        opacity: 0.7
                    }
                    Text {
                        x: 48
                        anchors.verticalCenter: parent.verticalCenter
                        text: "今日用电"
                        font.pixelSize: 14; color: cSub
                    }
                    Text {
                        anchors.right: parent.right
                        anchors.rightMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        text: bridge.state.today === null
                              ? "-- 度" : bridge.state.today + " 度"
                        font.pixelSize: 14; font.weight: Font.DemiBold
                        color: cText
                    }
                }

                Item { width: 1; height: 0 }
            }
        }

        // 指令失败提示(3 秒后由 state.error 自动清空)
        Rectangle {
            id: errTip
            // QVariantMap 里取不到的 key 会是 undefined, 直接和 "" 比较会误判成"有错误",
            // 结果只剩一个空的红圆点。统一先兜底成字符串再判断。
            property string msg: bridge.state.error || ""
            anchors.horizontalCenter: parent.horizontalCenter
            anchors.bottom: parent.bottom
            anchors.bottomMargin: 32
            width: errText.implicitWidth + 36
            height: 40
            radius: 20
            color: "#F5544E"
            z: 5
            visible: msg !== ""
            opacity: visible ? 1 : 0
            Behavior on opacity { NumberAnimation { duration: 150 } }
            Text {
                id: errText
                anchors.centerIn: parent
                text: errTip.msg
                font.pixelSize: 13
                color: "#FFFFFF"
            }
        }

        // ---------- 出风方向 弹层(与模式同形态: 底部贴边 + 遮罩) ----------
        Rectangle {
            anchors.fill: parent
            radius: 24
            color: "#BFEDEFF2"
            visible: bridge.state.dirPick
            MouseArea { anchors.fill: parent
                        onClicked: bridge.toggleFeature("wind_dir") }

            Rectangle {
                objectName: "dirSheet"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 283
                radius: 20
                color: cCard
                clip: true

                MouseArea { anchors.fill: parent }  // 吸收空白处点击

                Text {
                    x: 18; y: 16
                    text: "出风方向"
                    font.pixelSize: 15; font.weight: Font.DemiBold
                    color: cText
                }
                Rectangle { x: 18; y: 46; width: parent.width - 36
                            height: 1; color: "#EFF1F4" }

                // 上下风向: 5 档图标, 选中整格转蓝
                Text { x: 18; y: 58; text: "上下风向"
                       font.pixelSize: 12; color: "#9AA1A8" }
                Row {
                    x: 0; y: 76
                    width: parent.width
                    Repeater {
                        model: 5
                        delegate: Item {
                            id: vSlot
                            property int pos: index + 1
                            property bool on: bridge.state.vAngle === pos
                            width: parent.width / 5; height: 66
                            Image {
                                anchors.fill: parent
                                source: "icons/vdir" + vSlot.pos
                                        + (vSlot.on ? "_on" : "") + ".png"
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: bridge.setAngle(
                                    "v", vSlot.on ? 0 : vSlot.pos)
                            }
                        }
                    }
                }
                Rectangle { x: 18; y: 146; width: parent.width - 36
                            height: 1; color: "#EFF1F4" }

                // 左右风向: 5 档图标
                Text { x: 18; y: 156; text: "左右风向"
                       font.pixelSize: 12; color: "#9AA1A8" }
                Row {
                    x: 0; y: 174
                    width: parent.width
                    Repeater {
                        model: 5
                        delegate: Item {
                            id: hSlot
                            property int pos: index + 1
                            property bool on: bridge.state.hAngle === pos
                            width: parent.width / 5; height: 56
                            Image {
                                anchors.fill: parent
                                source: "icons/hdir" + hSlot.pos
                                        + (hSlot.on ? "_on" : "") + ".png"
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: bridge.setAngle(
                                    "h", hSlot.on ? 0 : hSlot.pos)
                            }
                        }
                    }
                }
                // 底部关闭条
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 53
                    color: "#F7F7F7"
                    Text {
                        anchors.centerIn: parent
                        text: "关闭弹层"
                        font.pixelSize: 15
                        color: cText
                    }
                    MouseArea { anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: bridge.toggleFeature("wind_dir") }
                }
            }
        }

        // ---------- 模式/风速 弹层 ----------
        Rectangle {
            anchors.fill: parent
            radius: 24
            color: "#BFEDEFF2"
            visible: pickerType !== ""
            MouseArea { anchors.fill: parent
                        onClicked: pickerType = "" }

            Rectangle {
                id: pickerSheet
                objectName: "pickerSheet"
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                height: 238
                radius: 20
                color: cCard
                clip: true

                MouseArea { anchors.fill: parent }  // 吸收空白处点击

                // 底部关闭条
                Rectangle {
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 53
                    color: "#F7F7F7"
                    Text {
                        anchors.centerIn: parent
                        text: "关闭弹层"
                        font.pixelSize: 15
                        color: cText
                    }
                    MouseArea { anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: pickerType = "" }
                }

                Text {
                    x: 18; y: 16
                    text: pickerType === "mode" ? "模式" : "风速"
                    font.pixelSize: 15; font.weight: Font.DemiBold
                    color: cText
                }

                Column {
                    x: 18; y: 54
                    width: parent.width - 36
                    spacing: 16

                    // 模式: 5 宫格
                    Grid {
                        visible: pickerType === "mode"
                        width: parent.width
                        columns: 3
                        spacing: 12
                        Repeater {
                            model: modeOpts
                            delegate: Rectangle {
                                property bool on:
                                    bridge.state.modeKey === modelData.k
                                width: (parent.width - 24) / 3
                                height: 44; radius: 12
                                color: on ? cBlue : "#F1F3F5"
                                Text {
                                    anchors.centerIn: parent
                                    text: modelData.n
                                    font.pixelSize: 14
                                    color: parent.on ? "#FFFFFF" : cText
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: bridge.setMode(modelData.k)
                                }
                            }
                        }
                    }

                    // 风速: 自动 + 0-100 滑条
                    Column {
                        visible: pickerType === "fan"
                        width: parent.width
                        spacing: 14

                        Row {
                            spacing: 12
                            Rectangle {
                                property bool on: bridge.state.fanKey === "auto"
                                width: 96; height: 40; radius: 12
                                color: on ? cBlue : "#F1F3F5"
                                Text {
                                    anchors.centerIn: parent
                                    text: "自动"
                                    font.pixelSize: 14
                                    color: parent.on ? "#FFFFFF" : cText
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: bridge.setFan("auto")
                                }
                            }
                            Text {
                                anchors.verticalCenter: parent.verticalCenter
                                text: (bridge.state.fanPct >= 0
                                       ? bridge.state.fanPct : 0) + "%"
                                font.pixelSize: 16; font.weight: Font.DemiBold
                                color: cText
                            }
                        }

                        Item {
                            id: fanSlider
                            width: parent.width; height: 32
                            property real pressX: -1

                            function valueAt(px) {
                                var r = Math.max(0, Math.min(1, px / fanSlider.width))
                                return Math.round(r * 100)
                            }
                            property real knobX: {
                                if (pressX >= 0) return pressX - 10
                                var pct = bridge.state.fanPct >= 0
                                          ? bridge.state.fanPct : 0
                                return pct / 100 * (fanSlider.width - 20)
                            }

                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: parent.width; height: 26; radius: 13
                                color: cTrack
                            }
                            Rectangle {
                                anchors.verticalCenter: parent.verticalCenter
                                width: Math.min(fanSlider.width, fanSlider.knobX + 23)
                                height: 26; radius: 13
                                color: cBlue
                            }
                            Rectangle {
                                width: 20; height: 20; radius: 10
                                anchors.verticalCenter: parent.verticalCenter
                                x: fanSlider.knobX
                                color: "#FFFFFF"
                            }
                            MouseArea {
                                anchors.fill: parent
                                anchors.margins: -14
                                cursorShape: Qt.PointingHandCursor
                                onPressed: function(mouse) {
                                    var px = Math.max(0, Math.min(
                                        fanSlider.width, mouseX - 14))
                                    fanSlider.pressX = px
                                }
                                onPositionChanged: function(mouse) {
                                    if (!pressed) return
                                    fanSlider.pressX = Math.max(
                                        0, Math.min(fanSlider.width, mouseX - 14))
                                }
                                onReleased: function(mouse) {
                                    bridge.setFanPct(fanSlider.valueAt(
                                        Math.max(0, Math.min(fanSlider.width,
                                                             mouseX - 14))))
                                    fanSlider.pressX = -1
                                }
                                onCanceled: fanSlider.pressX = -1
                            }
                        }
                        Text {
                            text: "松开滑条即生效"
                            font.pixelSize: 11; color: cDim
                        }
                    }
                }
            }
        }
    }
}
