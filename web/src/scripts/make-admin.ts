// Promote an existing account to admin (or back to a normal user).
//
//   pnpm make-admin you@example.com            → role: 'admin'
//   pnpm make-admin you@example.com --revoke   → role: 'user'
//
// The account must already exist: register it through /register first.
// This is the ONLY way to create an admin; there is no default admin password.
// Like seed.ts it runs outside SvelteKit (tsx), so it reads .env via dotenv.
import dotenv from 'dotenv';
// Load the shared workspace-root .env (../../ from web/src/scripts) regardless of cwd
dotenv.config({ path: new URL('../../../.env', import.meta.url) });
import mongoose from 'mongoose';
import { userSchema, type UserDoc } from '../lib/server/user-schema.js';

async function main() {
	const args = process.argv.slice(2);
	const revoke = args.includes('--revoke');
	const email = args.find((arg) => !arg.startsWith('--'))?.trim().toLowerCase();

	if (!email) {
		console.error('Usage: pnpm make-admin <email> [--revoke]');
		process.exit(1);
	}

	// Same fallback as lib/server/mongoose.ts: Atlas first, then local.
	const atlasUri = process.env.ATLAS_URI?.trim();
	const localUri = process.env.MONGODB_URI?.trim();
	const uri = atlasUri || localUri;
	const dbName =
		(atlasUri ? process.env.ATLAS_DB?.trim() : undefined) ||
		process.env.MONGODB_DB?.trim() ||
		'root-cause_db';
	if (!uri) {
		console.error('❌ Database configuration missing: Set ATLAS_URI or MONGODB_URI in .env');
		process.exit(1);
	}

	console.log(`🔌 Connecting to ${atlasUri ? 'Atlas' : 'Local'} MongoDB (${dbName})...`);
	const connection = await mongoose.createConnection(uri, { dbName }).asPromise();

	try {
		const User = connection.model<UserDoc>('User', userSchema);
		const role = revoke ? 'user' : 'admin';

		// runValidators: check the update against the schema (here: the role enum).
		// Mongoose only does that on save() by default, not on updates.
		const user = await User.findOneAndUpdate(
			{ email },
			{ role },
			// returnDocument 'after': give back the updated user, not the old version.
			{ returnDocument: 'after', runValidators: true }
		).lean();

		if (!user) {
			console.error(`❌ No account with email ${email}. Register it at /register first.`);
			process.exitCode = 1;
			return;
		}

		// No restart or re-login needed: hooks.server.ts reads the role on every request.
		console.log(`✅ ${user.name} <${user.email}> is now '${user.role}'.`);
	} finally {
		await connection.close();
	}
}

main().catch((error) => {
	console.error('❌ make-admin failed:', error);
	process.exit(1);
});
