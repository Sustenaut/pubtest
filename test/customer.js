// A test customer for pubtest's own suite, as register(api, { customers }) takes one:
// it names one repository, made up while recording. The same as
// tests/customers/pubtest_example_customer.py in Python.
export const made = [];

export const customer = {
  name: "pubtest.example",
  // Record mode only: the real names this scenario's logical ones stand for.
  setup() {
    made.push("pubtest-example-1");
    return { "the repository": "pubtest-example-1" };
  },
  // Record mode only, after the scenario, passed or failed.
  cleanup(tape, names) {
    made.splice(made.indexOf(names["the repository"]), 1);
  },
  steps: [
    ["Given", "the example customer's repository {string}", async (ctx, logical) => {
      const names = await ctx.tape.namesOf("pubtest.example");
      if (!(logical in names)) throw new Error(`the example customer has no ${logical}: ${JSON.stringify(names)}`);
    }],
  ],
};
