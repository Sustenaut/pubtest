// pubtest's own suite under cucumber-js.
import * as cucumber from "@cucumber/cucumber";
import { fromFetch, register } from "../js/index.js";
import { app, suite } from "./suite.js";

cucumber.setDefaultTimeout(60_000);
register(cucumber, { client: () => fromFetch(app) });
suite((kind, expression, fn) => cucumber[kind](expression, fn));
