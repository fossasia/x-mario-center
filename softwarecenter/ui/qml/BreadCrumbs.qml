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

Item {
    id: breadcrumbs

    property int animationDuration: 150
    property alias model: crumbslist.model
    property alias count: crumbslist.count

    function addCrumb(text, view, key) {
        crumbslist.model.append({ label: text, view: view, key: key })
    }

    function removeCrumb() {
        if (crumbslist.model.count > 1) {
            crumbslist.model.remove(crumbslist.model.count - 1)
        }
    }

    signal crumbClicked(int index)

    SystemPalette { id: activePalette }

    ListView {
        id: crumbslist
        interactive: false
        anchors.fill: parent
        anchors.margins: 10

        model: ListModel {}

        orientation: ListView.Horizontal

        delegate: Rectangle {
            id: delegate

            property real margins: 10
            property real fullWidth: text.paintedWidth + 2 * margins

            width: fullWidth
            height: crumbslist.height

            border.width: 1
            border.color: activePalette.shadow
            color: mousearea.containsMouse && !mousearea.pressed ? activePalette.light : activePalette.button

            clip: true

            Text {
                id: text
                anchors.verticalCenter: parent.verticalCenter
                x: parent.margins
                color: activePalette.buttonText
                text: label
            }

            MouseArea {
                id: mousearea
                anchors.fill: parent
                hoverEnabled: true
                onClicked: {
                    while ((crumbslist.model.count - 1) > index) {
                        breadcrumbs.removeCrumb()
                    }
                    breadcrumbs.crumbClicked(index)
                }
            }

            ListView.onAdd: SequentialAnimation {
                PropertyAction { target: delegate; property: "ListView.delayRemove"; value: true }
                PropertyAction { target: delegate; property: "width"; value: 0 }
                NumberAnimation { target: delegate; property: "width"; to: fullWidth; duration: breadcrumbs.animationDuration }
                PropertyAction { target: delegate; property: "ListView.delayRemove"; value: false }
            }
            ListView.onRemove: SequentialAnimation {
                PropertyAction { target: delegate; property: "ListView.delayRemove"; value: true }
                NumberAnimation { target: delegate; property: "width"; to: 0; duration: breadcrumbs.animationDuration }
                PropertyAction { target: delegate; property: "ListView.delayRemove"; value: false }
            }
        }
    }
}

