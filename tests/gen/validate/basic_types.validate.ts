import { assertType } from './helper';
import { BasicTypesModel, RPCMethods } from '../generated/basic_types';

type GetBasicTypesReturn = ReturnType<RPCMethods['get_basic_types']>;

const sample: BasicTypesModel = {
	an_int: 1,
	a_float: 1.23,
	a_str: 'hello',
	a_bool: true,
	a_none: null,
	any_type: 42 as any,
};

assertType<BasicTypesModel, Promise<BasicTypesModel>>(sample, null as unknown as GetBasicTypesReturn); 