// pubtest's own suite under quickpickle: the same suite steps as test/steps.js.
import * as quickpickle from "quickpickle";
import { register } from "../js/index.js";
import { app, suite } from "./suite.js";
import { fromFetch } from "../js/http.js";

register(quickpickle, { runner: "quickpickle", client: () => fromFetch(app) });
suite((kind, expression, fn) => quickpickle[kind](expression, (world, ...args) => fn.call(world, ...args)));
