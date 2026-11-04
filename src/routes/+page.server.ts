import { getDb } from '#lib/server/db.js';
import type { Actions, PageServerLoad } from './$types';

export interface Item {
	_id?: string;
	name: string;
	createdAt: Date;
}

export const load: PageServerLoad = async () => {
	const db = await getDb();
	const rawItems = await db
		.collection<Item>('items')
		.find()
		.sort({ createdAt: -1 })
		.limit(10)
		.toArray();

	// Convert ObjectId to string so SvelteKit can serialize it across the network boundary
	const items = rawItems.map((doc) => ({
		...doc,
		_id: doc._id.toString()
	}));

	return { items };
};

export const actions: Actions = {
	create: async ({ request }) => {
		const data = await request.formData();
		const name = data.get('name')?.toString()?.trim();

		if (!name) return { success: false };

		const db = await getDb();
		await db.collection('items').insertOne({
			name,
			createdAt: new Date()
		});

		return { success: true };
	}
};