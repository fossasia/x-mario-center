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
    signal shown
    signal hidden
    property alias duration: xAnimation.duration
    property alias running: xAnimation.running
    Behavior on x {
        NumberAnimation { id: xAnimation }
    }
    // Changing the 'visible' property badly messes with the active focus.
    // Changing the opacity preserves the focus, which is the desired behaviour.
    opacity: (x > -width) && (x < parent.width) ? 1.0 : 0.0
    onOpacityChanged: if (opacity == 0.0) hidden()
}

