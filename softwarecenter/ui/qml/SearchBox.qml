/*
 * Copyright 2011 Canonical Ltd.
 *
 * Authors:
 *  Olivier Tilloy <olivier@tilloy.net>
 *
 * This program is free software; you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation; version 3.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 */

import QtQuick 1.0

FocusScope {
    id: searchbox

    property alias text: textinput.text

    signal activated

    height: textinput.height + 7

    SystemPalette {
        id: activePalette
        colorGroup: SystemPalette.Active
    }

    Rectangle {
        anchors.fill: parent
        color: activePalette.base
        radius: 4
        border.color: parent.activeFocus ? activePalette.highlight : activePalette.mid
    }

    Image {
        id: searchicon
        source: "file:///usr/share/icons/Humanity/actions/16/edit-find.svg"
        asynchronous: true
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: 4
        fillMode: Image.PreserveAspectFit
        sourceSize.height: height
        opacity: searchmousearea.containsMouse ? 0.8 : 1.0

        MouseArea {
            id: searchmousearea
            anchors.fill: parent
            hoverEnabled: true
            onClicked: textinput.accepted()
        }
    }

    TextInput {
        id: textinput
        anchors.verticalCenter: parent.verticalCenter
        anchors.left: searchicon.right
        anchors.right: clearicon.left
        anchors.margins: 4
        focus: true
        selectByMouse: true
        onAccepted: if (textinput.text.length > 0) searchbox.activated()
    }

    Image {
        id: clearicon
        source: "file:///usr/share/icons/Humanity/actions/16/edit-clear.svg"
        asynchronous: true
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        anchors.margins: 4
        fillMode: Image.PreserveAspectFit
        sourceSize.height: height
        visible: textinput.text.length > 0
        opacity: clearmousearea.containsMouse ? 0.8 : 1.0

        MouseArea {
            id: clearmousearea
            anchors.fill: parent
            hoverEnabled: true
            onClicked: textinput.text = ""
        }
    }
}

