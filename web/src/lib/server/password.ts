// Password hashing with argon2id (the OWASP-recommended algorithm).
// Lives in lib/server/ so SvelteKit refuses to ever bundle it into browser code.
import { hash, verify } from '@node-rs/argon2';

// OWASP's minimum recommended settings for argon2id: 19 MiB memory, 2 iterations.
// Higher = slower to brute-force, but also slower for every real login.
const options = {
	memoryCost: 19456,
	timeCost: 2,
	outputLen: 32,
	parallelism: 1
};

// Returns a string like "$argon2id$v=19$m=19456,t=2,p=1$<salt>$<hash>".
// The salt and settings are stored inside the string, so we only save this one value.
export function hashPassword(password: string): Promise<string> {
	return hash(password, options);
}

// Re-hashes `password` using the salt/settings stored in `storedHash` and compares.
export function verifyPassword(storedHash: string, password: string): Promise<boolean> {
	return verify(storedHash, password);
}
