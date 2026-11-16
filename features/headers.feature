Feature: The worker's response headers
  worker/headers.js sets what the browser may load and keep. Every page
  holds the browser to this origin, Pyodide's files say what they are, and
  only the pinned files are kept, and only by this browser.

  Scenario Outline: Every file holds the browser to this origin
    When the worker answers for "<path>"
    Then its Content-Security-Policy allows connect-src 'self' and 'wasm-unsafe-eval'
    And it sends X-Content-Type-Options "nosniff"

    Examples:
      | path                                     |
      | /                                        |
      | /example/                                |
      | /vendor/pyodide/v314.0.0/pyodide.asm.wasm |
      | /example/assets/x.mjs                    |

  Scenario Outline: Pyodide's loader is JavaScript and its core WebAssembly
    When the worker answers for "<path>"
    Then it sends Content-Type "<type>"

    Examples:
      | path                                      | type            |
      | /vendor/pyodide/v314.0.0/pyodide.asm.mjs  | text/javascript |
      | /vendor/pyodide/v314.0.0/pyodide.asm.wasm | application/wasm |

  Scenario Outline: What's pinned is kept, by this browser only for the vendored wheels
    When the worker answers for "<path>"
    Then its Cache-Control matches "<pattern>"

    Examples:
      | path                                 | pattern              |
      | /vendor/pyodide/v314.0.0/numpy.whl   | ^private, .*immutable |
      | /example/assets/index-CgQsZfww.js    | immutable            |
      | /bundles/runtime-abc.gz              | immutable            |

  Scenario: The service worker is kept for an hour, by this browser
    When the worker answers for "/sw.js"
    Then it sends Cache-Control "private, max-age=3600"

  Scenario Outline: What changes with each build is not kept
    When the worker answers for "<path>"
    Then it sends no Cache-Control

    Examples:
      | path                        |
      | /example/public/build.json  |
      | /example/                   |

  Scenario: A page says nothing of its type, which the host gives
    When the worker answers for "/example/"
    Then it sends no Content-Type

  Scenario Outline: A failure at a pinned address isn't kept, and the rest stand as they are
    Given a response with status <status> and the headers of "/vendor/nothing.whl"
    When the worker passes it on
    Then its Cache-Control matches "<pattern>"

    Examples:
      | status | pattern    |
      | 404    | ^no-store$ |
      | 200    | immutable  |

  Scenario: A refusal keeps its own type
    Given a response with status 403, Content-Type "text/html; charset=utf-8" and Cache-Control "no-store"
    When the worker passes it on
    Then its Content-Type is "text/html; charset=utf-8"
