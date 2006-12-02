/*
 *  Camera.cpp
 *  openc2e
 *
 *  Created by Alyssa Milburn on Tue May 25 2004.
 *  Copyright (c) 2004 Alyssa Milburn. All rights reserved.
 *
 *  This library is free software; you can redistribute it and/or
 *  modify it under the terms of the GNU Lesser General Public
 *  License as published by the Free Software Foundation; either
 *  version 2 of the License, or (at your option) any later version.
 *
 *  This library is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
 *  Lesser General Public License for more details.
 *
 */

#include "Camera.h"
#include "CameraPart.h"
#include "World.h"
#include "Backend.h"

Camera::Camera() {
	// TODO: I set these to some high value due to stupidly-floating agents at (0, 0)
	// however, you'd think the proper engine wouldn't do this .. init order issues?
	x = 5000;
	y = 5000;
	metaroom = 0;
	panning = false;
}

MetaRoom * const Camera::getMetaRoom() {
	return world.map.getMetaRoom(metaroom);
}

void Camera::goToMetaRoom(unsigned int m) {
	metaroom = m;
	moveTo(getMetaRoom()->x(), getMetaRoom()->y());
}

void Camera::goToMetaRoom(unsigned int m, int _x, int _y, cameratransition transition) {
	metaroom = m;
	moveTo(_x, _y);
	// TODO: transition
	
	checkBounds();
}

void Camera::moveTo(int _x, int _y, panstyle pan) {
	// TODO: we don't break tracking according to trackingstyle.. atm updateTracking() calls this, also
	x = _x;
	y = _y;

	MetaRoom *m = world.map.metaRoomAt(x, y);
	if (m)
		metaroom = m->id;
	
	// TODO: panning
	
	checkBounds();
}

void MainCamera::moveTo(int _x, int _y, panstyle pan) {
	int xoffset = _x - x;
	int yoffset = _y - y;
	Camera::moveTo(_x, _y, pan);

	for (std::vector<AgentRef>::iterator i = floated.begin(); i != floated.end(); i++) {
		assert(*i);
		(*i)->moveTo((*i)->x + xoffset, (*i)->y + yoffset);
	}
}

void MainCamera::addFloated(AgentRef a) {
	assert(a);
	floated.push_back(a);
}

void MainCamera::delFloated(AgentRef a) {
	assert(a);
	std::vector<AgentRef>::iterator i = std::find(floated.begin(), floated.end(), a);
	if (i == floated.end()) return;
	floated.erase(i);
}

void Camera::trackAgent(AgentRef a, int xp, int yp, trackstyle s, cameratransition transition) {
	trackedagent = a;
	trackingstyle = s;
	updateTracking();
}

void Camera::checkBounds() {
	MetaRoom *m = getMetaRoom();
	if (!m) return;
	
	if (m->wraparound()) {
		// handle wrapping around, if necessary
		if (x < (int)m->x()) {
			moveTo(x + m->width(), y);
		} else if (x > (int)m->x() + (int)m->width()) {
			moveTo(x - m->width(), y);
		}
	} else {
		// refuse to move beyond the boundaries
		if (x < (int)m->x()) {
			moveTo(m->x(), y);
		} else if (x + getWidth() > m->x() + m->width()) {
			moveTo(m->x() + m->width() - getWidth(), y);
		}
	}

	// refuse to move beyond the boundaries
	if (y < (int)m->y()) {
		moveTo(x, m->y());
	} else if (y + getHeight() > m->y() + m->height()) {
		moveTo(x, m->y() + m->height() - getHeight());
	}
}

void Camera::tick() {
	updateTracking();
}

void Camera::updateTracking() {
	if (!trackedagent) return;

	int x = trackedagent->x - (getWidth() / 2);
	int y = trackedagent->y - (getHeight() / 2);
	moveTo(x, y);
}

unsigned int const MainCamera::getWidth() {
	if ((!getMetaRoom()) || (backend->getMainSurface()->getWidth() < getMetaRoom()->width()))
		return backend->getMainSurface()->getWidth();
	else
		return getMetaRoom()->width();
}

unsigned int const MainCamera::getHeight() {
	if ((!getMetaRoom()) || (backend->getMainSurface()->getHeight() < getMetaRoom()->height()))
		return backend->getMainSurface()->getHeight();
	else
		return getMetaRoom()->height();
}

unsigned int const PartCamera::getWidth() {
	// TODO: update from ZOOM values
	return part->cameraWidth();
}

unsigned int const PartCamera::getHeight() {
	// TODO: update from ZOOM values
	return part->cameraHeight();
}

/* vim: set noet: */
