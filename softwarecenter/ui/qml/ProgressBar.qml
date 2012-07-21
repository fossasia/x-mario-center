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

Rectangle {
    property int progress: 0 // between 0 and 100

    SystemPalette {
        id: activePalette
        colorGroup: SystemPalette.Active
    }

    color: activePalette.base

    Rectangle {
        color: activePalette.highlight
        anchors.left: parent.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: progress / 100 * parent.width
    }

    Rectangle {
        anchors.fill: parent
        color: "transparent"
        border.width: 1
        border.color: activePalette.shadow
    }
}

