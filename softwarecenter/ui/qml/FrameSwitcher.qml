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
    id: frameSwitch

    property int duration: 200
    property alias currentIndex: frames.currentIndex
    property alias count: frames.count

    clip: true

    ListModel {
        id: frames
        property int currentIndex: -1
    }

    onWidthChanged: {
        for (var i = 0; i < frames.count; i++) {
            frames.get(i).frame.width = frameSwitch.width
        }
        if (frames.count > 0) {
            frames.get(0).frame.x = -frameSwitch.width * frames.currentIndex
        }
    }

    function pushFrame(frame) {
        frame.duration = frameSwitch.duration
        frames.append({ frame: frame })
        frame.parent = frameSwitch
        frame.width = frame.parent.width
        frame.anchors.top = frame.parent.top
        frame.anchors.bottom = frame.parent.bottom
        if (frames.count == 1) {
            frame.x = 0
            frame.focus = true
            frames.currentIndex = 0
        } else {
            frame.anchors.left = frames.get(frames.count - 2).frame.right
        }
    }

    function currentFrame() {
        if (frames.count > 0) {
            return frames.get(frames.currentIndex).frame
        } else {
            return null
        }
    }

    function changeIndex(newIndex) {
        if (frames.count <= 1) return
        if (frames.currentIndex == newIndex) return
        if (newIndex < 0 || newIndex >= frames.count) return
        frameConnection.target = frames.get(0).frame
        frames.get(0).frame.x = -frameSwitch.width * newIndex
        frames.currentIndex = newIndex
    }

    function goToFrame(frame) {
        for (var i = 0; i < frames.count; i++) {
            if (frames.get(i).frame == frame) {
                changeIndex(i)
                break
            }
        }
    }

    Connections {
        id: frameConnection
        target: null
        onRunningChanged: {
            if (!frameConnection.target.running) {
                frameConnection.target = null
                currentFrame().shown()
                currentFrame().focus = true
            }
        }
    }
}

