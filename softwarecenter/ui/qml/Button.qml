/*
 * Copyright 2011 Canonical Ltd.
 *
 * Authors:
 *  Michael Vogt <mvo@ubuntu.com>
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

Rectangle {
    property string text: "ButtonText"
    signal clicked
    
    SystemPalette { id: activePalette }

    Text {
        id: buttontxt
        anchors.centerIn: parent
        text: parent.text
        color: activePalette.buttonText
    }

    width: buttontxt.width + 10
    height: buttontxt.height + 10

    radius: 4
    border.width: 1
    border.color: activePalette.shadow
    color: mousearea.containsMouse && !mousearea.pressed ? activePalette.light : activePalette.button
    
    MouseArea {
        id: mousearea
        anchors.fill: parent
        hoverEnabled: true
        onClicked: parent.clicked()
    }
}

