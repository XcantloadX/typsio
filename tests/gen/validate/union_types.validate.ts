import { assertType } from './helper';
import { UnionTypesModel, RPCMethods } from '../generated/union_types';

type GetUnionsReturn = ReturnType<RPCMethods['get_unions']>;

const unions: UnionTypesModel = {
	classic_union: 'value',
	optional_type: null,
	new_union_syntax: 123,
};

assertType<UnionTypesModel, Promise<UnionTypesModel>>(unions, null as unknown as GetUnionsReturn); 