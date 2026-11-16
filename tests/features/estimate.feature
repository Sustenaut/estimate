Feature: The estimate models, the helpers their pages use, and the site build (): the notebooks run natively, inputs come from a publication bundle when it has them, links match pub.sustenaut.eu, the wheel is the same bytes every time, and an exported page loads nothing from another origin

  Scenario: Models follow the contract
    Then models follow the contract

  Scenario: Notebook runs
    Then notebook runs

  Scenario: Example result is fixed by the seed
    Then example result is fixed by the seed

  Scenario: Bundle values replace the models
    Then bundle values replace the models

  Scenario: Model values stay when the bundle has none
    Then model values stay when the bundle has none

  Scenario: Bundle values in another unit are not used
    Then bundle values in another unit are not used

  Scenario: Several rows need a row
    Then several rows need a row

  Scenario: The real bundle is read when built
    Then the real bundle is read when built

  Scenario: Links match what pub site serves
    Then links match what pub site serves

  Scenario: Rounding
    Then rounding

  Scenario: Citation
    Then citation

  Scenario: Wheel is reproducible and installable
    Then wheel is reproducible and installable

  Scenario: Vendor lock pins everything
    Then vendor lock pins everything

  Scenario: Marimo matches the pins
    Then marimo matches the pins

  Scenario: A bundle holds each file where its index says
    Then a bundle holds each file where its index says

  Scenario: Exported page loads only from this site
    Then exported page loads only from this site
