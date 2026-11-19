// pubtest's own suite under quickpickle: the same suite steps as test/steps.js.
import * as quickpickle from "quickpickle";
import { register } from "../js/index.js";
import { customer } from "./customer.js";
import { app, network, suite } from "./suite.js";
import { fromFetch } from "../js/http.js";

register(quickpickle, { runner: "quickpickle", client: () => fromFetch(app), customers: [customer], network });
suite((kind, expression, fn) => quickpickle[kind](expression, (world, ...args) => fn.call(world, ...args)));
