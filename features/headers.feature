Feature: The worker's response headers
  worker/headers.js sets what the browser may load and keep. Every page
  holds the browser to this origin, Pyodide's files say what they are, and
  only the pinned files are kept, and only by this browser. A GET here is
  answered with the headers the worker gives that path.

  Scenario Outline: Every file holds the browser to this origin
    When I GET "<path>"
    Then the answer's "Content-Security-Policy" includes "connect-src 'self'"
    And the answer's "Content-Security-Policy" includes "'wasm-unsafe-eval'"
    And the answer's "X-Content-Type-Options" is "nosniff"

    Examples:
      | path                                     |
      | /                                        |
      | /example/                                |
      | /vendor/pyodide/v314.0.0/pyodide.asm.wasm |
      | /example/assets/x.mjs                    |

  Scenario Outline: Pyodide's loader is JavaScript and its core WebAssembly
    When I GET "<path>"
    Then the answer's "Content-Type" is "<type>"

    Examples:
      | path                                      | type            |
      | /vendor/pyodide/v314.0.0/pyodide.asm.mjs  | text/javascript |
      | /vendor/pyodide/v314.0.0/pyodide.asm.wasm | application/wasm |

  Scenario Outline: What's pinned is kept, by this browser only
    When I GET "<path>"
    Then the answer's "Cache-Control" is "private, max-age=31536000, immutable"

    Examples:
      | path                                 |
      | /vendor/pyodide/v314.0.0/numpy.whl   |
      | /example/assets/index-CgQsZfww.js    |
      | /bundles/runtime-abc.gz              |

  Scenario: The service worker is kept for an hour, by this browser
    When I GET "/sw.js"
    Then the answer's "Cache-Control" is "private, max-age=3600"

  Scenario Outline: What changes with each build is not kept
    When I GET "<path>"
    Then the answer has no "Cache-Control"

    Examples:
      | path                        |
      | /example/public/build.json  |
      | /example/                   |

  Scenario: A page says nothing of its type, which the host gives
    When I GET "/example/"
    Then the answer has no "Content-Type"

  Scenario Outline: A failure at a pinned address isn't kept, and the rest stand as they are
    Given a response with status <status> and the headers of "/vendor/nothing.whl"
    When the worker passes it on
    Then the result's "status" is "<status>"
    And the result's "headers.cache-control" is "<cache>"
    And the result's "headers.content-type" is "<type>"

    Examples:
      | status | cache                                | type                      |
      | 404    | no-store                             | text/plain; charset=utf-8 |
      | 200    | private, max-age=31536000, immutable | text/plain;charset=UTF-8  |

  Scenario: A refusal keeps its own type
    Given a response with status 403, Content-Type "text/html; charset=utf-8" and Cache-Control "no-store"
    When the worker passes it on
    Then the result's "headers.content-type" is "text/html; charset=utf-8"
    And the result's "headers.cache-control" is "no-store"
