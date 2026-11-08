// src/lib/server/sessions.ts
// Session logic: create a session at login, look it up on every request
// (hooks.server.ts), delete it at logout. Plus the cookie helpers.
import { createHash, randomBytes } from 'node:crypto';
import type mongoose from 'mongoose';
import type { Cookies } from '@sveltejs/kit';
import type { Types } from 'mongoose';
import { getConnection } from './mongoose.js';
import { getUserModel } from './users.js';
import { sessionSchema, type SessionDoc } from './session-schema.js';
import type { UserRole } from './user-schema.js';

export const SESSION_COOKIE = 'session';

const DAY_MS = 24 * 60 * 60 * 1000;
const SESSION_LIFETIME_MS = 30 * DAY_MS;
// When less than this is left, push the expiry back to a full 30 days.
const RENEW_WHEN_LESS_THAN_MS = 15 * DAY_MS;

// What the rest of the app gets to know about the logged-in user (locals.user).
// Deliberately no passwordHash.
export interface SessionUser {
	id: string;
	name: string;
	email: string;
	role: UserRole;
}

export async function getSessionModel(): Promise<mongoose.Model<SessionDoc>> {
	// populate('userId') needs the User model registered on the same connection.
	await getUserModel();
	const connection = await getConnection();
	// Reuse the compiled model after an HMR reload (avoids OverwriteModelError), like resources.ts.
	const Session =
		connection.models.Session ?? connection.model<SessionDoc>('Session', sessionSchema);
	await Session.init(); // waits for the unique + TTL indexes
	return Session;
}

// 32 random bytes → 43-character string. Unguessable; this goes into the cookie.
function generateToken(): string {
	return randomBytes(32).toString('base64url');
}

// What we store in the DB. If the DB ever leaked, these can't be used as cookies.
function hashToken(token: string): string {
	return createHash('sha256').update(token).digest('hex');
}

// Called at login/register. Returns the token for the cookie (shown only once:
// the DB only ever sees its hash).
export async function createSession(userId: Types.ObjectId) {
	const Session = await getSessionModel();
	const token = generateToken();
	const expiresAt = new Date(Date.now() + SESSION_LIFETIME_MS);
	await Session.create({ tokenHash: hashToken(token), userId, expiresAt });
	return { token, expiresAt };
}

// Called on every request with the cookie value.
// Returns the user + (possibly extended) expiry, or null = not logged in.
export async function validateSession(token: string) {
	const Session = await getSessionModel();
	const tokenHash = hashToken(token);

	// One query for the session, populate does the second (the user) for us.
	const session = await Session.findOne({ tokenHash })
		.populate<{
			// role is optional here: users created before the role field existed don't have it.
			userId: { _id: Types.ObjectId; name: string; email: string; role?: UserRole } | null;
		}>(
			'userId',
			'name email role' // only these fields: never load passwordHash here
		)
		.lean();

	if (!session) return null;

	// The user was deleted but the session still exists.
	if (!session.userId) {
		await Session.deleteOne({ tokenHash });
		return null;
	}

	const now = Date.now();
	// Expired, but the TTL cleanup (once a minute) hasn't removed it yet.
	if (session.expiresAt.getTime() <= now) {
		await Session.deleteOne({ tokenHash });
		return null;
	}

	// Active user: keep them logged in. Extend to a full 30 days again.
	let expiresAt = session.expiresAt;
	if (expiresAt.getTime() - now < RENEW_WHEN_LESS_THAN_MS) {
		expiresAt = new Date(now + SESSION_LIFETIME_MS);
		await Session.updateOne({ tokenHash }, { expiresAt });
	}

	const user: SessionUser = {
		id: String(session.userId._id),
		name: session.userId.name,
		email: session.userId.email,
		// Missing role (older accounts) = normal user. Never default to admin.
		role: session.userId.role ?? 'user'
	};
	return { user, expiresAt };
}

// Called at logout.
export async function deleteSession(token: string): Promise<void> {
	const Session = await getSessionModel();
	await Session.deleteOne({ tokenHash: hashToken(token) });
}

// SvelteKit's defaults already apply: httpOnly (page JavaScript can't read it),
// secure (HTTPS only, relaxed in dev) and path '/'.
export function setSessionCookie(cookies: Cookies, token: string, expiresAt: Date): void {
	cookies.set(SESSION_COOKIE, token, {
		path: '/',
		sameSite: 'lax', // not sent on POSTs from other sites → helps against CSRF
		expires: expiresAt
	});
}

export function deleteSessionCookie(cookies: Cookies): void {
	cookies.delete(SESSION_COOKIE, { path: '/' });
}
