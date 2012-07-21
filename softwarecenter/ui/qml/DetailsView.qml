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

FocusScope {
    id: detailsview

    Rectangle {
        id: detailsframe
        anchors.fill: parent
        color: activePalette.base

        CloudsHeader {
            anchors.top: parent.top
            anchors.left: parent. left
            anchors.right: parent.right
        }

        Image {
            id: largeiconimg
            height: 64
            width: height
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.margins: 15
            sourceSize.height: height
            sourceSize.width: width
            source: list.currentItem != null ? list.currentItem.icon : ""
            asynchronous: true
        }

        Text {
            id: titletxt
            anchors.top: parent.top
            anchors.left: largeiconimg.right
            anchors.right: parent.right
            anchors.margins: 15
            height: 25
            font.pointSize: 20
            font.bold: true
            text: list.currentItem != null ? list.currentItem.appname : ""
        }

        Text {
            id: headertxt
            anchors.top: titletxt.bottom
            anchors.topMargin: 5
            anchors.left: largeiconimg.right
            anchors.right: parent.right
            anchors.margins: 15
            height: 10
            font.pointSize: 9
            text: list.currentItem != null ? list.currentItem.summary : ""
        }

        Stars {
            id: headerstars
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.margins: 12
            height: 32
            ratings_average: list.currentItem != null ? list.currentItem.ratingsaverage : 0
        }
        Text {
            id: headernrreviews
            anchors.top: headerstars.bottom
            anchors.horizontalCenter: headerstars.horizontalCenter
            text: list.currentItem != null ? qsTr("%1 reviews").arg(list.currentItem.ratingstotal) : 0
        }

        Rectangle {
            id: installrect
            anchors.top: largeiconimg.bottom

            color: "lightblue"
            height: installbtn.height + 12
            width: parent.width

            Button {
                id: installbtn
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                anchors.rightMargin: 12

                text: list.currentItem == null ? "" : list.currentItem.installed ? qsTr("Remove") : qsTr("Install")

                onClicked: {
                    if (list.currentItem.installed) 
                        list.model.removePackage(list.currentItem.pkgname)
                    else
                        list.model.installPackage(list.currentItem.pkgname)
                }
            }

            ProgressBar {
                id: progressbar
                anchors.fill: installbtn
                width: 200
                progress: list.currentItem != null ? list.currentItem.installremoveprogress : 0
                visible: (list.currentItem != null) && (list.currentItem.installremoveprogress != -1)
            }
        }

        Text {
            id: desctxt
            anchors.top: installrect.bottom
            anchors.topMargin: 50
            anchors.left: parent.left
            anchors.right: screenshotthumb.left
            anchors.margins: 15
            text: list.currentItem != null ? list.currentItem.description : ""
            wrapMode: Text.Wrap
        }

        Image {
            id: screenshotthumb
            anchors.top: installrect.bottom
            anchors.topMargin: 50
            anchors.right: parent.right
            anchors.margins: 15
            height: 100
            width: 150
            sourceSize.height: height
            sourceSize.width: width

            MouseArea {
                anchors.fill: parent
                onClicked: {
                    if (screenshotthumb.status == Image.Ready) {
                        screenshotview.loadScreenshot("http://screenshots.ubuntu.com/screenshot/" + list.currentItem.pkgname)
                    }
                }
            }
        }

        // reviews part
        Text {
            anchors.top: desctxt.bottom
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 15
            id: reviewsheadertxt
            text: qsTr("Reviews")
        }

        Rectangle {
            id: reviewslistframe
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 15
            anchors.top: reviewsheadertxt.bottom
            anchors.bottom: parent.bottom
            clip: true

            ScrollBar {
                id: reviewsVerticalScrollBar
                width: 6; 
                height: reviewslist.height - 10
                orientation: Qt.Vertical
                
                anchors.right: reviewslistframe.right
                position: reviewslist.visibleArea.yPosition
                pageSize: reviewslist.visibleArea.heightRatio
            }

            ListView {
                id: reviewslist
                spacing: 5
                width: parent.width - 10
                height: parent.height - 10
                anchors.centerIn: parent

                model: reviewslistmodel

                delegate: Rectangle {
                    property string summary: _summary
                    property string review_text: _review_text
                    property string rating: _rating
                    property string reviewer_displayname: _reviewer_displayname
                    property string date_created: _date_created

                    // FIXME: can this be automatically calculated?
                    //        if I ommit it its getting cramped togehter 
                    //        in funny ways
                    height: reviewsummarytxt.height + reviewtxt.height + 20
                    width: reviewslist.width

                    Stars {
                        id: stars
                        height: 16
                        ratings_average: rating
                    }
                    Text {
                        id: reviewsummarytxt
                        text: summary
                        font.bold: true
                        anchors.left: stars.right
                        anchors.right: whowhentxt.left
                        anchors.margins: 5
                        elide: Text.ElideRight
                    }
                    Text {
                        id: whowhentxt
                        text: qsTr("%1, %2").arg(reviewer_displayname).arg(date_created)
                        anchors.right: parent.right
                        color: "grey"
                    }
                    Text {
                        id: reviewtxt
                        text: review_text
                        wrapMode: Text.Wrap
                        anchors.left: parent.left
                        anchors.right: parent.right
                        anchors.top: stars.bottom
                        anchors.topMargin: 5
                    }
                }
            }
        }
    }

    function loadThumbnail() {
        screenshotthumb.source = "http://screenshots.ubuntu.com/thumbnail/" + list.currentItem.pkgname
    }
    function unloadThumbnail() {
        screenshotthumb.source = ""
    }
    function loadReviews() {
         reviewslistmodel.getReviews(list.currentItem.pkgname)
    }
    function hideScreenshot() {
        screenshotview.fadeOut()
    }

    Rectangle {
        id: screenshotview
        width: parent.width
        height: parent.height
        anchors.left: detailsview.left
        opacity: 0.0
        color: activePalette.window

        Behavior on opacity {
            NumberAnimation {
                duration: 300
            }
        }

        function loadScreenshot(url) {
            screenshotfullimg.source = url
            fadeIn()
        }

        function fadeIn() {
            opacity = 1.0
        }

        function fadeOut() {
            opacity = 0.0
        }

        Rectangle {
            id: screenshotframe
            anchors.fill: parent
            anchors.margins: 10
            color: activePalette.base
            radius: 5

            Rectangle {
                anchors.left: parent.left
                anchors.right: parent.right
                height: 150
                radius: parent.radius
                gradient: Gradient {
                    GradientStop { position: 0.0; color: "#B2CFE7" }
                    GradientStop { position: 1.0; color: "white" }
                }
                Image {
                    anchors.top: parent.top
                    anchors.right: parent.right
                    source: "file:///usr/share/software-center/images/clouds.png"
                    asynchronous: true
                }
            }
            
            Text {
                id: screenshottitle
                anchors.top: parent.top
                anchors.left: parent.left
                anchors.right: parent.right
                anchors.margins: 15
                height: 25
                font.pointSize: 14
                font.bold: true
                text: list.currentItem != null ? "Screenshot for " + list.currentItem.appname : ""
            }

            Image {
                id: screenshotfullimg
                anchors.top: screenshottitle.bottom
                anchors.right: parent.right
                anchors.margins: 20
                width: parent.width - 50
                sourceSize.width: width

                asynchronous: true

                MouseArea {
                    anchors.fill: parent
                    onClicked: {
                        screenshotview.fadeOut()
                    }
                }
            }
            Button {
                id: screenshotbackbtn
                text: qsTr("Done")

                anchors.bottom: parent.bottom
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.margins: 15

                onClicked: {
                    screenshotview.fadeOut()
                }
            }
        }
    }
}
