import { assertType } from './helper';
import { NestedModel, TopLevelModel, RPCMethods } from '../generated/pydantic_models';

type GetModelReturn = ReturnType<RPCMethods['get_model']>;

const nested: NestedModel = { id: 1, name: '2233', detail: 'x' };
const top: TopLevelModel = { id: 1, nested };

assertType<TopLevelModel, Promise<TopLevelModel>>(top, null as unknown as GetModelReturn); 