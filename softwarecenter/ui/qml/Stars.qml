/*
 * Copyright 2011 Canonical Ltd.
 *
 * Authors:
 *  Olivier Tilloy <olivier@tilloy.net>
 *  Michael Vogt <mvo@ubuntu.com>
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

Row {
    property double ratings_average

    Repeater {
        height: parent.height
        model: Math.floor(ratings_average)
        Image {
            source: (height <= 16) ? "star-small-full.png" : "star-large-full.png"
            smooth: true
            height: parent.height
            width: height
        }
    }
    Image {
        visible: Math.floor(ratings_average) != Math.ceil(ratings_average)
        source: (height <= 16) ? "star-small-half.png" : "star-large-half.png"
        smooth: true
        height: parent.height
        width: height
    }
    Repeater {
        height: parent.height
        model: 5 - Math.ceil(ratings_average)
        Image {
            source: (height <= 16) ? "star-small-empty.png" : "star-large-empty.png"
            smooth: true
            height: parent.height
            width: height
        }
    }
}

