import { assertType } from './helper';
import { GlobModel1, GlobModel2, RPCMethods } from '../generated/glob_test';

type FuncFromGlob1Return = ReturnType<RPCMethods['func_from_glob_1']>;
type FuncFromGlob2Return = ReturnType<RPCMethods['func_from_glob_2']>;

const sample1: GlobModel1 = {
  prop1: 'hello'
};

const sample2: GlobModel2 = {
  prop2: true
};

assertType<GlobModel1, Promise<number>>(sample1, null as unknown as FuncFromGlob1Return);
assertType<GlobModel2, Promise<string>>(sample2, null as unknown as FuncFromGlob2Return);