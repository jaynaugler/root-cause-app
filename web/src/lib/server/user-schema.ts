// src/lib/server/user-schema.ts
// The Mongoose schema for the `users` collection. Like resource-schema.ts, it has
// no SvelteKit imports, so scripts (tsx) could import it directly.
import mongoose from 'mongoose';

// 'admin' can only be set from the server side (scripts/make-admin.ts), never
// through the register form: createUser() doesn't accept a role at all.
export const USER_ROLES = ['user', 'admin'] as const;
export type UserRole = (typeof USER_ROLES)[number]; // 'user' | 'admin'

export interface UserDoc {
	name: string;
	email: string;
	passwordHash: string; // argon2id hash from password.ts; never send it to the browser
	role: UserRole;
	createdAt: Date;
}

export const userSchema = new mongoose.Schema<UserDoc>(
	{
		name: { type: String, required: true, trim: true, minlength: 1, maxlength: 100 },
		email: {
			type: String,
			required: true,
			// unique is NOT a validator: it tells Mongoose to create a unique index
			// in MongoDB. The database itself then rejects duplicates (error 11000).
			unique: true,
			// "Bob@X.com " is saved (and queried) as "bob@x.com"
			lowercase: true,
			trim: true,
			maxlength: 254,
			match: /^[^\s@]+@[^\s@]+\.[^\s@]+$/
		},
		passwordHash: { type: String, required: true },
		// enum: any other value is a validation error. default: every new account is 'user'.
		role: { type: String, enum: USER_ROLES, required: true, default: 'user' },
		createdAt: { type: Date, required: true, default: () => new Date() }
	},
	{ strict: 'throw' } // unknown fields are an error, same as resourceSchema
);
