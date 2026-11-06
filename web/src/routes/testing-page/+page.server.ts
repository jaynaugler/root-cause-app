import { getDb } from '#lib/server/db.js';
import { fail } from '@sveltejs/kit';
import { ObjectId } from 'mongodb';
import { z } from 'zod';
import type { Actions, PageServerLoad } from './$types';

export interface Item {
	_id: ObjectId;
	name: string;
	createdAt: Date;
}

// 1. Define the validation schema
const itemSchema = z.object({
	name: z.string()
		.trim()
		.min(3, { message: 'Name must be at least 3 characters.' })
		.max(50, { message: 'Name cannot exceed 50 characters.' })
});

export const load: PageServerLoad = async () => {
	const db = await getDb();
	const rawItems = await db
		.collection<Item>('items')
		.find()
		.sort({ createdAt: -1 })
		.limit(10)
		.toArray();

	const items = rawItems.map((doc) => ({
		...doc,
		_id: String(doc._id)
	}));

	return { items };
};

export const actions: Actions = {
	create: async ({ request }) => {
		const data = await request.formData();
		const rawName = data.get('name');

		// 2. Validate with Zod
		const result = itemSchema.safeParse({ name: rawName });

		if (!result.success) {
			// Flatten the Zod errors into a simple object (e.g. { name: ["Error message"] })
			const errors = result.error.flatten().fieldErrors;
			
			// 3. Return a 400 status with the errors and the original input to repopulate the form
			return fail(400, { 
				errors, 
				name: rawName?.toString() 
			});
		}

		// 4. Safe to insert into MongoDB
		const db = await getDb();
		await db.collection('items').insertOne({
			name: result.data.name,
			createdAt: new Date()
		});

		return { success: true };
	}
};