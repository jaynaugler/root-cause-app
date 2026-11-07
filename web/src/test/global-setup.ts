// Runs ONCE before all test files: starts a real, temporary MongoDB in memory.
// No Atlas, no Docker, nothing left behind: it's deleted when the tests finish.
import { MongoMemoryServer } from 'mongodb-memory-server';
import type { TestProject } from 'vitest/node';

export default async function setup(project: TestProject) {
	const mongo = await MongoMemoryServer.create();

	// Hand the connection string to the test files (read with inject('mongoUri')).
	project.provide('mongoUri', mongo.getUri());

	// The returned function runs once after all tests: stop and delete the DB.
	return async () => {
		await mongo.stop();
	};
}

// Tells TypeScript what inject('mongoUri') returns.
declare module 'vitest' {
	export interface ProvidedContext {
		mongoUri: string;
	}
}
