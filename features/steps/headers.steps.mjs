// Steps for headers.feature: worker/headers.js, called as the worker calls it.
import assert from "node:assert/strict";
import { Given, Then, When } from "@cucumber/cucumber";
import { failuresNotKept, headersFor } from "../../worker/headers.js";

When("the worker answers for {string}", function (path) {
  this.headers = headersFor(path);
});

Then("its Content-Security-Policy allows connect-src 'self' and 'wasm-unsafe-eval'", function () {
  const csp = this.headers["Content-Security-Policy"];
  assert.match(csp, /connect-src 'self'/);
  assert.match(csp, /'wasm-unsafe-eval'/);
});

Then("it sends X-Content-Type-Options {string}", function (value) {
  assert.equal(this.headers["X-Content-Type-Options"], value);
});

Then("it sends Content-Type {string}", function (value) {
  assert.equal(this.headers["Content-Type"], value);
});

Then("it sends Cache-Control {string}", function (value) {
  assert.equal(this.headers["Cache-Control"], value);
});

Then("it sends no Cache-Control", function () {
  assert.equal(this.headers["Cache-Control"], undefined);
});

Then("it sends no Content-Type", function () {
  assert.equal(this.headers["Content-Type"], undefined);
});

Given("a response with status {int} and the headers of {string}", function (status, path) {
  this.response = new Response("x", { status, headers: headersFor(path) });
});

Given("a response with status {int}, Content-Type {string} and Cache-Control {string}", function (status, type, cache) {
  this.response = new Response("x", { status, headers: { "Content-Type": type, "Cache-Control": cache } });
});

When("the worker passes it on", function () {
  const passed = failuresNotKept(this.response);
  this.headers = Object.fromEntries(passed.headers.entries());
  this.headers["Cache-Control"] = passed.headers.get("Cache-Control") ?? undefined;
  this.headers["Content-Type"] = passed.headers.get("Content-Type") ?? undefined;
});

Then("its Cache-Control matches {string}", function (pattern) {
  assert.match(this.headers["Cache-Control"], new RegExp(pattern));
});

Then("its Content-Type is {string}", function (value) {
  assert.equal(this.headers["Content-Type"], value);
});
