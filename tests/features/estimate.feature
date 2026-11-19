Feature: The estimate models, the helpers their pages use, and the site build
  The notebooks run natively, inputs come from a publication bundle when it
  has them, links match pub.sustenaut.eu, the wheel is the same bytes every
  time, and an exported page loads nothing from another origin.

  Scenario Outline: A model names itself and its version
    When I read the description of the model "<model>"
    Then the result includes "name"
    And the result includes "version"

    Examples:
      | model   |
      | example |

  Scenario Outline: A model says what it puts out
    When I read the outputs of the model "<model>"
    Then the result is not "[]"
    And each item of the result has "name"
    And each item of the result has "unit"
    And each item of the result has "description"

    Examples:
      | model   |
      | example |

  Scenario Outline: A model's parameters are three-point estimates, each from a publet
    When I read the parameters of the model "<model>"
    Then each item of the result has "name"
    And each item of the result has "unit"
    And each item of the result has "low"
    And each item of the result has "likely"
    And each item of the result has "high"
    And each item of the result has "publet"
    And each item of the result has "low", "likely" and "high" in that order
    And each item of the result has "publet" as text that is not empty

    Examples:
      | model   |
      | example |

  Scenario Outline: A notebook runs
    When I run the notebook "<notebook>"
    Then it is not refused

    Examples:
      | notebook             |
      | notebooks/example.py |

  Scenario: The example's result is fixed by the seed
    When I sample the example model with the site's generator
    Then the result is what the example model gives with the seed 42
    And the result rises from above 40 to below 90

  Scenario Outline: Bundle values replace the models
    Given a scratch directory
    And a bundle "bundle" whose basil row holds "<cell>"
    When I read the parameter with "publet" set to "<publet>" against the bundle "bundle"
    Then the result's "low" is "50"
    And the result's "likely" is "70"
    And the result's "high" is "100"
    And the result's "status" is "from the publication"

    Examples:
      | cell                                     | publet              |
      | [50, 70, 100]                            | pub:sha2-256:claim  |
      | [50, 70, 100]                            | harvest per tray    |
      | {"low": 50, "likely": 70, "high": 100}   | pub:sha2-256:claim  |
      | {"low": 50, "likely": 70, "high": 100}   | harvest per tray    |

  Scenario: Model values stay when the bundle has none
    Given a scratch directory
    And a bundle "bundle" whose basil row holds "null"
    When I read the parameter against the bundle "bundle"
    Then the result's "low" is "1.0"
    And the result's "likely" is "2.0"
    And the result's "high" is "3.0"
    And the result's "status" is "placeholder (not measured yet)"

  Scenario: Model values stay when there is no bundle
    When I read the parameter against no bundle
    Then the result's "low" is "1.0"
    And the result's "status" is "placeholder (no publication bundle next to this page)"

  Scenario: Model values stay when the bundle does not hold the publet
    Given a scratch directory
    And a bundle "bundle" whose basil row holds "null"
    When I read the parameter with "publet" set to "pub:sha2-256:elsewhere" against the bundle "bundle"
    Then the result's "low" is "1.0"
    And the result's "status" is "placeholder (publet not in the publication)"

  Scenario: Bundle values in another unit are not used
    Given a scratch directory
    And a bundle "bundle" whose basil row holds "[50, 70, 100]"
    When I read the parameter with "unit" set to "kg/{tray}" against the bundle "bundle"
    Then the result's "low" is "1.0"
    And the result's "status" is "placeholder (publication states g/{tray}, model needs kg/{tray})"

  Scenario: Several rows need a row
    Given a scratch directory
    And a bundle "bundle" whose basil row holds "[50, 70, 100]"
    And the bundle "bundle"'s radish row holds "[1, 2, 3]"
    When I read the parameter with "row" set to "null" against the bundle "bundle"
    Then the result's "low" is "1.0"
    And the result's "status" is "placeholder (2 values in the publication; name the row)"

  Scenario: The real bundle is read when built
    Given a scratch directory
    And the pinned publication bundled into "bundle" by a pub with `bundle`
    When I read the example model's parameters against the bundle "bundle"
    Then the result has 1 parameter
    And the result's "0.status" is "placeholder (not measured yet)"

  Scenario Outline: Links match what pub site serves
    When I ask for the link to "<publet>"
    Then the result is "<link>"

    Examples:
      | publet           | link                                            |
      | pub:sha2-256:abc | https://pub.sustenaut.eu/o/pub:sha2-256:abc/    |
      | {tray}           | https://pub.sustenaut.eu/def/%7Btray%7D/        |
      | harvest per tray | https://pub.sustenaut.eu/def/harvest%20per%20tray/ |

  Scenario: The input table links each input to its publet
    When I make the input table of the example model
    Then the result includes "(https://pub.sustenaut.eu/o/pub:sha2-256:xgkogmxvbj72gf7k2pqqfpis6xq7b6ozlcsyquqchvrluidhybpa/)"
    And the result includes "| placeholder |"

  Scenario Outline: A number is rounded to three significant figures
    When I round <number>
    Then the result is "<rounded>"

    Examples:
      | number    | rounded |
      | 62.681313 | 62.7    |
      | 0.0123456 | 0.0123  |
      | 123456    | 123000  |

  Scenario Outline: A number is shown to three significant figures
    When I format <number>
    Then the result is "<shown>"

    Examples:
      | number    | shown   |
      | 62.681313 | 62.7    |
      | 40.0      | 40.0    |
      | 123456    | 123,000 |

  Scenario: The rounding is stated
    When I ask for the rounding note
    Then the result includes "3 significant figures"

  Scenario: A native run cites the commit and no wheel
    When I cite a native run
    Then the result's "wheel" is "null"
    And the result's "commit" is "unknown" or a 40-character hash

  Scenario: A built page cites its wheel's sha256
    Given a scratch directory
    And a file "public/build.json" holding:
      """
      {"wheel": "estimate-0.1.0-py3-none-any.whl", "sha256": "abababababababababababababababababababababababababababababababab", "commit": "cccccccccccccccccccccccccccccccccccccccc"}
      """
    When I cite the build in "."
    Then the result's "sha256" is "abababababababababababababababababababababababababababababababab"

  Scenario: A built page's citation names its wheel's sha256
    Given a scratch directory
    And a file "public/build.json" holding:
      """
      {"wheel": "estimate-0.1.0-py3-none-any.whl", "sha256": "abababababababababababababababababababababababababababababababab", "commit": "cccccccccccccccccccccccccccccccccccccccc"}
      """
    When I write the citation of the build in "."
    Then the result includes "sha256 `abababababababababababababababababababababababababababababababab"

  Scenario: The wheel is the same bytes every time
    Given a scratch directory
    When I build the wheel into "1"
    And I build the wheel into "2"
    Then the files "1/estimate-0.1.0-py3-none-any.whl" and "2/estimate-0.1.0-py3-none-any.whl" are the same bytes

  Scenario: The wheel holds the package and its record
    Given a scratch directory
    When I list what the wheel built into "w" holds
    Then the result includes "estimate/site.py"
    And the result includes "estimate/models/example.py"
    And the result includes "estimate-0.1.0.dist-info/RECORD"

  Scenario: The vendor lock pins everything
    When I read the vendor lock
    Then it pins the marimo and Pyodide versions build.py names
    And it pins every package build.py names, each by sha256, with what it depends on
    And it pins Pyodide's core files and the npm packages build.py names

  Scenario: Marimo matches the pins
    When I ask marimo for its version
    Then the result is the marimo version build.py names
    And requirements.lock pins marimo at the version build.py names

  Scenario: A bundle holds each file where its index says
    Given a scratch directory
    And a file "a" holding "first"
    And a file "b" holding "second file"
    When I pack "a" as "/vendor/a.whl" and "b" as "/example/public/o/pub:x.json"
    Then the packed bundle holds each file where its index says
    And packing them again gives the same bytes

  Scenario: An exported page loads only from this site
    Given a scratch directory
    When I export "notebooks/example.py" into "page"
    Then it is not refused
    And the file "page/index.html" includes "data-pyodide-lockfile-url="../vendor/pyodide/"
    And "page/index.html" points Pyodide at the version build.py vendors
    And no script in "page/assets" loads from a third party
    And the file "page/CLAUDE.md" does not exist
