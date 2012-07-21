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
    property alias searchQuery: searchbox.text
    property alias breadcrumbs: breadcrumbs
    property bool searchBoxVisible: true

    signal crumbClicked(int index)
    signal searchActivated

    height: searchbox.height + 2 * 10 // 10px margins

    SystemPalette {
        id: activePalette
        colorGroup: SystemPalette.Active
    }

    Rectangle {
        anchors.fill: parent
        color: activePalette.window
    }

    Rectangle {
        height: 1
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        color: activePalette.mid
    }

    // TODO: back/forward buttons

    BreadCrumbs {
        id: breadcrumbs
        anchors.fill: parent
        onCrumbClicked: parent.crumbClicked(index)
    }

    SearchBox {
        id: searchbox
        width: 160
        anchors.verticalCenter: parent.verticalCenter
        anchors.right: parent.right
        anchors.margins: 10
        onActivated: parent.searchActivated()
        opacity: parent.searchBoxVisible ? 1.0 : 0.0
        focus: parent.searchBoxVisible
    }
}

