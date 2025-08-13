import { assertType } from './helper';
import { CollectionTypesModel, RPCMethods } from '../generated/collection_types';

type GetCollectionsReturn = ReturnType<RPCMethods['get_collections']>;

const collections: CollectionTypesModel = {
	str_list: ['a', 'b'],
	num_dict: { a: 1, b: 2 },
	int_set: [1, 2, 3],
};

assertType<CollectionTypesModel, Promise<CollectionTypesModel>>(collections, null as unknown as GetCollectionsReturn); 