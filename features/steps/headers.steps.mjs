// Steps for headers.feature: worker/headers.js, called as the worker calls it.
// Sending a request and checking the answer and the result are pubtest's.
import * as cucumber from "@cucumber/cucumber";
import { register } from "@sustenaut/pubtest";
import { Answer } from "@sustenaut/pubtest/http";
import { failuresNotKept, headersFor } from "../../worker/headers.js";

const { Given, Then, When } = cucumber;

// A request is answered with the headers the worker gives its path.
register(cucumber, { client: () => async (method, path) => new Answer(200, headersFor(path), "") });

Then("the answer's {string} includes {string}", function (name, text) {
  const value = this.pubtest.answer?.header(name);
  if (!value?.includes(text)) throw new Error(`the answer's ${name} is ${JSON.stringify(value)}, without ${text}`);
});

Given("a response with status {int} and the headers of {string}", function (status, path) {
  this.response = new Response("x", { status, headers: headersFor(path) });
});

Given("a response with status {int}, Content-Type {string} and Cache-Control {string}", function (status, type, cache) {
  this.response = new Response("x", { status, headers: { "Content-Type": type, "Cache-Control": cache } });
});

When("the worker passes it on", async function () {
  await this.attempt(() => {
    const passed = failuresNotKept(this.response);
    return { status: passed.status, headers: Object.fromEntries(passed.headers.entries()) };
  });
});
