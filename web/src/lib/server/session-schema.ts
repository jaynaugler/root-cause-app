// src/lib/server/session-schema.ts
// The Mongoose schema for the `sessions` collection: one document per logged-in
// browser/device. No SvelteKit imports, same as the other *-schema.ts files.
import mongoose, { Schema, type Types } from 'mongoose';

export interface SessionDoc {
	tokenHash: string; // SHA-256 of the cookie token, never the token itself
	userId: Types.ObjectId; // → users._id
	expiresAt: Date;
}

export const sessionSchema = new mongoose.Schema<SessionDoc>(
	{
		tokenHash: { type: String, required: true, unique: true },
		// ref: 'User' lets .populate('userId') fetch the user together with the session.
		// index: makes "all sessions of this user" fast (e.g. a future "log out everywhere").
		userId: { type: Schema.Types.ObjectId, ref: 'User', required: true, index: true },
		// expires: 0 creates a TTL index: MongoDB deletes the document once expiresAt
		// has passed (its cleanup runs about once a minute).
		expiresAt: { type: Date, required: true, expires: 0 }
	},
	{ strict: 'throw' }
);
