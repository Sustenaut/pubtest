// pubtest's own suite under cucumber-js.
import * as cucumber from "@cucumber/cucumber";
import { fromFetch, register } from "../js/index.js";
import { customer } from "./customer.js";
import { app, network, suite } from "./suite.js";

cucumber.setDefaultTimeout(60_000);
register(cucumber, { client: () => fromFetch(app), customers: [customer], network });
suite((kind, expression, fn) => cucumber[kind](expression, fn));
