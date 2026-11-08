// src/lib/server/users.ts
// The `users` Mongoose model and the queries auth needs.
import type mongoose from 'mongoose';
import { getConnection } from './mongoose.js';
import { hashPassword } from './password.js';
import { userSchema, type UserDoc } from './user-schema.js';

export async function getUserModel(): Promise<mongoose.Model<UserDoc>> {
	const connection = await getConnection();
	// Reuse the compiled model after an HMR reload (avoids OverwriteModelError), like resources.ts.
	const User = connection.models.User ?? connection.model<UserDoc>('User', userSchema);
	// Waits until Mongoose has created the indexes (the unique email index).
	// Only slow the very first time; afterwards it returns immediately.
	await User.init();
	return User;
}

// .lean() returns a plain object instead of a full Mongoose document:
// faster, and what we want for reading.
export async function findUserByEmail(email: string) {
	const User = await getUserModel();
	return User.findOne({ email: email.trim().toLowerCase() }).lean();
}

// Returns the new user's id, or 'email-taken' if the unique index rejected the insert.
export async function createUser(input: { name: string; email: string; password: string }) {
	const User = await getUserModel();
	try {
		const user = await User.create({
			name: input.name,
			email: input.email, // the schema lowercases + trims it
			passwordHash: await hashPassword(input.password)
			// createdAt: filled by the schema default; _id: created automatically
		});
		return user._id;
	} catch (err) {
		// 11000 = duplicate key: an account with this email already exists.
		if ((err as { code?: number }).code === 11000) return 'email-taken' as const;
		throw err;
	}
}
