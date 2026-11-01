# CRSP flags used by the momentum pipeline

Full frozen metadata dictionary: 774 values across 62 flag types. This guide maps fields to types: codes have meaning only within their field.

## Processing policy

- Formation/t-13 prices: require period-end PE, matching price date, TR or BA, and positive finite price/equity. LA, MI, NT and non-price/delisting substitutes cannot establish formation value. NS is usable only if its actual price date equals the actual period-end date (including the database start in December 1925).
- BA is a valid bid-ask price, not missing. Red/yellow completeness alone does not justify excluding every record. Holding returns remain unchanged by the formation-value screen.
- Previous-date flags describe the return starting point. They do not establish that the current period-end value is missing.
- Monthly CR/MP/DE, incomplete IP and gap GP require different period interpretation; no numeric return is silently converted into a new single-period return.
- Daily D1/D2/D3/D4/DU each mean one trading session: weekends/holidays are valid. P1-P9 span multiple trading sessions and cannot be relabelled as one daily return.
- Ordinary missing-stock return zero is a user valuation convention, not a CRSP/KF rule. Missing corporate-action or terminal information is not resolved by that convention.
- Monthly delisting A/P is already included; G excluded; M missing; V partial. Daily dlydelflg Y is a separate component, not the monthly aggregate DE flag. Known terminal value is included once; unknown remains unknown.

## Fields and all their label definitions

### `mthdtflg` — flag type AG

- **ED — End Date:** Date Flag only: The date is the end date of the security (this can never be previous date flag)
- **LA — Last Available:** The last available non-missing value for the period.  See the corresponding price date field for the date of the value used.
- **MI — Missing/Not Tracked:** There are no prices for the entire period, the price and the return are set to missing
- **NS — New Security:** The price is from the beginning of date of the security
- **NT — Not Tracked:** Previous Date Flag only: Previous period is before the start of the security
- **PE — Period-End:** The date used is the last trading day of the period

### `mthprevdtflg` — flag type AG

- **ED — End Date:** Date Flag only: The date is the end date of the security (this can never be previous date flag)
- **LA — Last Available:** The last available non-missing value for the period.  See the corresponding price date field for the date of the value used.
- **MI — Missing/Not Tracked:** There are no prices for the entire period, the price and the return are set to missing
- **NS — New Security:** The price is from the beginning of date of the security
- **NT — Not Tracked:** Previous Date Flag only: Previous period is before the start of the security
- **PE — Period-End:** The date used is the last trading day of the period

### `mthprcflg` — flag type PC

- **BA — Bid Ask Average:** BA     Bid Ask Average
- **DA — Delisting Amount (no Delisting Price):** DA     Delisting Amount (no Delisting Price)
- **DM — Delisting Price/Amount Missing:** DM     Delisting Price/Amount Missing
- **DP — Delisting Price:** DP     Delisting Price
- **GP — Gap - more than 10 periods:** GP     Gap - more than 10 periods
- **MI — Missing - Prior to BegDt:** MI     Missing - Prior to BegDt
- **MP — Missing Price:** MP     Missing Price
- **NA — Not Applicable:** NA     Not Applicable
- **NS — New Security:** NS     New Security
- **NT — Not Tracked:** NT     Not Tracked
- **TR — Closing Trade Price:** TR     Closing Trade Price

### `mthprevprcflg` — flag type PC

- **BA — Bid Ask Average:** BA     Bid Ask Average
- **DA — Delisting Amount (no Delisting Price):** DA     Delisting Amount (no Delisting Price)
- **DM — Delisting Price/Amount Missing:** DM     Delisting Price/Amount Missing
- **DP — Delisting Price:** DP     Delisting Price
- **GP — Gap - more than 10 periods:** GP     Gap - more than 10 periods
- **MI — Missing - Prior to BegDt:** MI     Missing - Prior to BegDt
- **MP — Missing Price:** MP     Missing Price
- **NA — Not Applicable:** NA     Not Applicable
- **NS — New Security:** NS     New Security
- **NT — Not Tracked:** NT     Not Tracked
- **TR — Closing Trade Price:** TR     Closing Trade Price

### `mthretflg` — flag type AR

- **CR — Compounded Return:** Daily returns are compounded into a period return from the last trading day of the previous period to the last trading day of this period, with no missing returns.
- **DE — Compounded Return - Delists:** Daily returns are compounded into a period return from the last trading day of the previous period to the delisting date with no missing returns and, when appropriate, the delisting return is also compounded into this return.  See delist flag.
- **GP — Gap Between Prices is too Large:** Period return is set to missing, because the price on the Price Date is after a gap in the daily returns data of greater than ten trading days for the security
- **IP — Compounded Return - Incomplete Period:** Period return is compounded from the daily returns, but it is an unusual circumstance that does not match any of the other flag conditions
- **MP — Compounded Return - Missing Prices(s):** Daily returns are compounded into a period return from the last trading day of the previous period to the last trading day of this period, with one or more missing returns
- **NS — New Security:** Daily returns are compounded into a period return from the beginning date of the security until the last trading day of this period with no missing returns
- **NT — Not Tracked:** Period return is set to missing, because there is no return data for the entire period in the daily file

### `mthdelflg` — flag type DE

- **A — Amount - Return Included:** Delisting return based on distribution amount(s) is included in the aggregate return
- **G — Gap - Return Excluded:** Delisting return is excluded from aggregate return, because the value is more than 10 day from the delisting date
- **M — Missing- Return Excluded:** Delisting return is excluded from aggregate return, because the delisting return is missing
- **N — Not Applicable:** Not Applicable - Security is active during this period
- **P — Price- Return Included:** Delisting return based on Next Available Price is included in the aggregate return
- **V — Value Partial - Return Included:** Partial value delisting return based on one or more non-missing distribution amounts is included in the aggregate return, but one or more other distributions has missing values

### `mthcompflg` — flag type CF

- **G — Green:** Green - This is the most common code and indicates the most complete aggregate returns with no missing prices or return anywhere in the period.  These returns, but not necessarily volumes, can be used for most purposes without further filtering.
- **R — Red:** Red - This is a relatively uncommon code and indicates rows that are included for completeness and transparency, but are most often excluded from analysis.  The rows include periods with multiple unusual situations or is entirely missing.
- **Y — Yellow:** Yellow - This is a relatively uncommon code and indicates rows with that are often used in analysis, but ones that should be examined for special handling before use.  The majority of these rows are the first and last period a security has a return.

### `mthcompsubflg` — flag type CG

- **G1 — Green-1:** Green-1 - This code indicates that subset of Green rows that also have complete volumes and price volumes and distribution during the period, and can be used for almost all purposes without further processing.
- **G2 — Green-2:** Green-2 - This code includes the rows impacted the limitations of CRSP's NASDAQ volume data or that have one or more distributions that impact returns.  If using volume, price*volume, or prices in your analysis, these rows may require special processing.
- **G3 — Green-3:** Green-3 - This code is a small subset of the Green rows, and indicates rows that have no missing prices or returns, but have share adjustment factors or unexpected missing volumes.  For some analysis this rows might need special processing to be excluded.
- **R1 — Red-1:** Red-1 - This code indicates the rows have has non-missing returns, no distributions, and no gaps, but that the return and volume, and price*volume are from an incomplete period.  These rows often require special processing to be used in analysis.
- **R2 — Red-2:** Red-2 - This code indicates rows that have non-missing returns, but that have multiple situations, often including a two-week or greater gap in prices.  These rows may include useful data, but almost always require special processing for use in analysis.
- **R3 — Red-3:** Red-3 - This code indicates that the daily returns are missing for the entire period. The aggregate return is set to missing, and are usually when a security is off a CRSP-tracked exchange or is a security that started trading on the last day of a period.
- **Y1 — Yellow-1:** Yellow-1 - This code indicates a row that is a new security during the period that has no distributions and no missing prices.  It may or may not have missing volumes.  These rows are often included in analysis, but are not a full period return.
- **Y2 — Yellow-2:** Yellow-2 - This code indicates a security delisted during the period and has no distributions, no missing prices, and a non-missing delisting returns.  Volumes may be missing. These rows are often included in analysis, but are not a full period return.
- **Y3 — Yellow-3:** Yellow-3 - This code has a return for the entire period with no gap, but they likely require special processing, because they include some combination of special conditions, distributions, new or delisted security, missing prices or delisting return.

### `dlyprcflg` — flag type PC

- **BA — Bid Ask Average:** BA     Bid Ask Average
- **DA — Delisting Amount (no Delisting Price):** DA     Delisting Amount (no Delisting Price)
- **DM — Delisting Price/Amount Missing:** DM     Delisting Price/Amount Missing
- **DP — Delisting Price:** DP     Delisting Price
- **GP — Gap - more than 10 periods:** GP     Gap - more than 10 periods
- **MI — Missing - Prior to BegDt:** MI     Missing - Prior to BegDt
- **MP — Missing Price:** MP     Missing Price
- **NA — Not Applicable:** NA     Not Applicable
- **NS — New Security:** NS     New Security
- **NT — Not Tracked:** NT     Not Tracked
- **TR — Closing Trade Price:** TR     Closing Trade Price

### `dlyretmissflg` — flag type RM

- **DG — Delisting Price GT 10 periods from delisting date:** DG     Delisting Price is more than 10 periods from the Delisting Date
- **DM — Delisting Price/Amount Missing:** DM     Delisting Price/Amount Missing
- **DP — Delisting Pending:** DP     Delisting Pending
- **GP — Gap Between Prices Too Large:** GP     Gap Between Prices Too Large
- **MP — Missing Price:** MP     Missing Price
- **MV — Missing Corporate Action Value:** MV     Missing Corporate Action Value
- **NA — Not Applicable:** NA     Not Applicable
- **NS — New Security:** NS     New Security
- **NT — Not Tracked:** NT     Not Tracked
- **RA — Return after Not Tracked period:** RA     Return after Not Tracked period

### `dlyretdurflg` — flag type RD

- **D1 — 1 Trading Day and 1 Calendar Day:** D1     1 Trading Day & 1 Calendar Day; no Holiday, no Weekend
- **D2 — 1 Trading Day and 2 Calendar Days:** D2     1 Trading Day & 2 Calendar Days; return with holiday (market closed or Saturday trading)
- **D3 — 1 Trading Day and 3 Calendar Days:** D3     1 Trading Day & 3 Calendar Days; return over weekend
- **D4 — 1 Trading Day and 4 Calendar Days:** D4     1 Trading Day & 4 Calendar Days; return over 3-day weekend
- **DD — Other Daily Delisting Return Duration:** DD     Other Daily Delisting Return Duration
- **DU — 1 Trading Day & 5 or more Calendar Days:** DU     1 Trading Day & 5 or more Calendar Days
- **MR — Missing Return:** MR     Missing Return
- **P1 — Multi-period 2 Trading Days or Months:** P1     Multi-period 2 Trading Days or Months
- **P2 — Multi-period 3 Trading Days or Months:** P2     Multi-period 3 Trading Days or Months
- **P3 — Multi-period 4 Trading Days or Months:** P3     Multi-period 4 Trading Days or Months
- **P4 — Multi-period 5 Trading Days or Months:** P4     Multi-period 5 Trading Days or Months
- **P5 — Multi-period 6 Trading Days or Months:** P5     Multi-period 6 Trading Days or Months
- **P6 — Multi-period 7 Trading Days or Months:** P6     Multi-period 7 Trading Days or Months
- **P7 — Multi-period 8 Trading Days or Months:** P7     Multi-period 8 Trading Days or Months
- **P8 — Multi-period 9 Trading Days or Months:** P8     Multi-period 9 Trading Days or Months
- **P9 — Multi-period 10 Trading Days or Months:** P9     Multi-period 10 Trading Days or Months

### `dlydelflg` — flag type YN

- **N — No:** No - The flag is false - See Item Info file for more details on use
- **Y — Yes:** Yes - The flag is true - See Item Info file for more details on use

### `conditionaltype` — flag type CT

- **N/A — Not Applicable:** N/A    Not Applicable
- **NT — Not Tracked:** NT     Not Tracked
- **NW — Non-Leading When Issued:** NW     Non-Leading When Issued
- **RW — Regular Way:** RW     Regular Way
- **WI — When Issued:** WI     When Issued

### `tradingstatusflg` — flag type TS

- **A — Active:** A      Active
- **D — Delisted:** D      Delisted
- **H — Halted:** H      Halted
- **S — Suspended:** S      Suspended
- **X — Unknown or Unavailable:** X      Unknown or Unavailable

### `primaryexch` — flag type EC

- **A — NYSE American:** A      NYSE American
- **B — BATS:** B      BATS
- **I — IEX:** I      IEX
- **N — NYSE:** N      NYSE
- **Q — NASDAQ:** Q      NASDAQ
- **R — NYSE ARCA:** R      NYSE ARCA
- **X — Unknown:** X      Unknown

## Provenance

Definitions are read from the authorized frozen CRSP `metaflaginfo` cache. Official reference pattern: https://www.crsp.org/wp-content/uploads/appendix/FlagType_AG.html (replace AG with the flag type). New full-sample screening outputs are separate from historical cached results.

## Current-web additions and mode selection

The frozen metadata contains 774 labels. The current official PC web page additionally lists SU (suspended) and HA (halted); both fail the TR/BA formation-price allowlist. These additions do not modify the frozen raw cache.

`screen_formation_values` is used by `scripts/formation_quality_backtest.py`. `zero_regular_dm_checked` protects missing special values and multi-session daily records. Legacy cached `zero_regular_dm` results retain their original reproducible meaning. Independent stock-risk backtests must obtain daily observations for the newly formed memberships before using the updated formation screen; old selected-stock daily caches are not silently treated as a complete new universe.

## Classification fields

### `securitytype` — S3

- **DERV — Derivative:** DERV   Derivative

- **EQTY — Equity:** EQTY   Equity

- **FUND — Fund:** FUND   Fund

- **N/A — Not Applicable:** N/A    Not Applicable

### `securitysubtype` — S2

- **ATR — Americus Trust:** ATR    Americus Trust

- **CEF — Closed End Fund:** CEF    Closed End Fund

- **COM — Common:** COM    Common

- **ETF — Exchange Traded Fund:** ETF    Exchange Traded Fund

- **ETV — Exchange Traded Vehicle:** ETV    Exchange Traded Vehicle

- **UNK — Unknown or Unspecified:** UNK    Unknown or Unspecified

### `sharetype` — S4

- **AD — American Depositary Receipt:** AD     American Depositary Receipt

- **CE — Certificate:** CE     Certificate

- **N/A — Not Applicable:** N/A    Not Applicable

- **NS — No special share type specified:** NS     No special share type specified

- **SB — Shares of Beneficial Interest:** SB     Shares of Beneficial Interest

- **UG — Units General:** UG     Units General

### `issuertype` — IT

- **ACOR — Assumed Corporation:** ACOR   Assumed Corporation

- **CORP — Corporation:** CORP   Corporation

- **REIT — REIT:** REIT   REIT

### `usincflg` — YN

- **N — No:** No - The flag is false - See Item Info file for more details on use

- **Y — Yes:** Yes - The flag is true - See Item Info file for more details on use

## Current primary scenario versus strict diagnostics

The current primary stock-account and risk series use `reconstructed_zero_missing`
(monthly) and `zero_missing_reconstructed` (daily). They retain known numeric
components, include recorded delisting components once and assume missing stock
components/unknown terminal increments zero. Multi-session numeric components are
booked once at the provider endpoint. These are explicit project valuation
assumptions, not a CRSP/KF rule or confirmed final recovery. The strict policies
described above remain diagnostic artifacts; their missing values are never
replaced with KF risk. See Notebook 03 and WML_PIPELINE.md for the full current
specification and diagnostic counters.
