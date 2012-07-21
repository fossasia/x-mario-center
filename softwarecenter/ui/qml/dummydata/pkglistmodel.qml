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

ListModel {
    ListElement {
        _appname: "Gestionnaire de Mises à Jour"
        _pkgname: "update-manager"
        _icon: "/usr/share/icons/Humanity/categories/32/applications-other.svg"
        _summary: "Voir et installer les mises à jour disponibles"
        _installed: true
        _description: "This is the GNOME apt update manager. It checks for updates and lets the user choose which to install."
        _ratings_total: 4.12
        _ratings_average: 17
        _installremoveprogress: -1
    }
    ListElement {
        _appname: "Unity 2D"
        _pkgname: "unity-2d"
        _icon: "/usr/share/icons/Humanity/categories/32/applications-other.svg"
        _summary: "Unity interface for non-accelerated graphics cards"
        _installed: true
        _description: "The Unity 2D interface installs a fully usable 2D session and provides the common configuration files and defaults. Installing this package will offer a session called Unity 2D in your login manager. Unity 2D is designed to run smoothly without any graphics acceleration."
        _ratings_total: 4.68
        _ratings_average: 25
        _installremoveprogress: -1
    }
    ListElement {
        _appname: "Neverball"
        _pkgname: "neverball"
        _icon: "file:///usr/share/app-install/icons/neverball.xpm"
        _summary: "Un jeu d'arcade 3D avec une balle"
        _installed: false
        _description: "Dans la grande tradition de Marble Madness et Super Monkey Ball, Neverball vous fait guider une boule roulant à travers des territoires dangereux. Balancez-vous sur des ponts étroits, naviguez dans des labyrinthes, roulez sur des plate-formes en mouvement et évitez des pousseurs et des glisseurs pour arriver au but. Courrez contre la montre pour collecter les pièces pour obtenir des boules supplémentaires."
        _ratings_total: 4.53
        _ratings_average: 15
        _installremoveprogress: -1
    }

    function setCategory(category) {
        console.log("setting category to", category)
    }
}

