# Campus Customs Ops Floor: Dashboard Design

The dashboard (`frontend/`, React + Vite + TypeScript) is where a person watches five AI agents run the shop's back office and holds the one thing they can't do themselves: approve a payment. Every choice below serves one of three jobs:

1. **Follow the work**: who is doing what, right now.
2. **Decide on money**: what's waiting on you and what it will cost.
3. **Trust the result**: what each agent contributed and what it left on the board.

The name "Ops Floor" frames the screen as a trading-floor-style operations room: tickets come in on the left, the team works in the middle, and the money desk sits on the right. The tagline under the title says the deal plainly: *"Five agents run the back office. You hold the checkbook."*

---

## Layout

Three columns on a wide screen, read left to right in the order work actually flows:

| Column | What's there | Why |
|---|---|---|
| **Left: Ticket board** | One card per ticket (#101, #102, #103) with status pill, requester, item, and a "payments waiting on you" flag | You see the whole queue at once and pick one. The card stays put while you scroll, so switching tickets is always one click away. |
| **Center: The stage** | The selected ticket's header (hero), the agent roster, the live feed, then "Who did what" and "On the board" side by side | Everything about *one* ticket in reading order: what was asked → who's on it → what they're doing → what they concluded → what they wrote. |
| **Right: Money desk** | Checking balance with a meter, then the approval queue | Money decisions are always visible, whichever ticket you're looking at, because all three tickets compete for the same $3,400. |

- **The hero** puts the one action that matters in its top-right corner. That's a large pink **Start the agent team** button, which changes to *Agents working…* with a running timer, then *Waiting on your OK*, and finally a green **Resolved** check. The requester's original words are quoted, so you can judge the agents against what was actually asked.
- **A four-step progress tracker** (Open → Agents working → Needs your OK → Resolved) sits under every ticket header. The current step glows pink and finished steps turn green, so progress reads at a glance without parsing status words.
- **Responsive:**
  - Below 1280px, the money desk moves under the stage as two side-by-side panels.
  - Below 860px, everything stacks into one column, and the ticket board becomes a horizontal strip you swipe through.
  - Nothing scrolls sideways at phone width (checked at 375px).

## How users tell the agents apart

Each agent has **three cues together**, so no one depends on color alone (helpful for color-blind users):

| Agent | Color | Icon | Role line |
|---|---|---|---|
| Boss | hot pink `#ff4fa3` (the brand color: the Boss leads) | crown | Routes work, makes the call |
| Inventory | teal `#38d9c5` | box | Stock, shortfalls, vendors |
| Accounting | amber `#ffc35a` (money = gold) | coins | Cash, margins, approvals |
| Facilities | violet `#a98bff` | storefront | Lease, rent, landlord |
| Customer Service | sky blue `#5cb6ff` | speech bubble | Drafts replies |

That color-and-icon pair follows the agent everywhere:
- **Agent roster:** a row of five avatars under the ticket header. The agent working *right now* lifts up, gets a pulsing ring and reads "working now…". Agents who took part stay lit, and agents not involved fade to 45%. You can see at a glance that a rent ticket only needed Boss, Facilities and Accounting.
- **Live feed:**
  - Messages are chat bubbles edged in the speaker's color.
  - Tool calls read as plain sentences ("Inventory **checked stock** `check_stock_shortfall` sku CC-HOOD-NAVY · size M").
  - Tool results fold away under a small "result" tag, so the feed stays readable but nothing is hidden.
- **Hand-offs** get their own card: *Boss → Facilities*, with both avatars, a gradient from one agent's color to the other's, and the exact task in quotes. Work a teammate does after a hand-off is indented one step, so the delegation chain (Boss → Facilities → Accounting) is visible as shape, not just text.
- **"Who did what"** gives each agent a card topped with its color stripe. The card shows the agent's own summary of its work, who asked it, who it handed off to, the tools it used (with counts) and its token use. The Boss's final call sits above the cards as the verdict, with a **For you** list of exactly what the human must do.

## How resolved tickets appear

- On the ticket board, a resolved card gets a soft green wash and a tilted **RESOLVED ✓** rubber stamp. When a ticket *becomes* resolved while you're watching, the stamp slams down (a quick scale-in), the ticket header pulses green twice, and a toast says "Ticket #102 is resolved."
- The ticket header swaps its button for a large green check and "Resolved," and the progress tracker's last dot lights up.
- A ticket that is only waiting on a payment shows **Waiting on your OK** in amber instead of a "run again" button. It also says the ticket resolves on its own once you've decided every request, so you're never left wondering what's next.

## How cash appears

- **One big number:** the checking balance in large tabular figures, so digits don't jiggle as they change.
- **It moves when money moves.** After you approve a payment, the balance *counts down* to the new figure, which shows the change instead of just swapping numbers. A red "−$2,400.00" chip drops in beside it and fades after a few seconds.
- **A meter** under the balance shows what's left of the starting cash in pink. The part already promised to pending requests is hatched in amber, so you can see whether everything waiting would fit.
- **Two plain lines:** *Waiting on approval* and *If you approve everything*. The second turns amber when approving everything would overdraw the account.
- **A "Paid out" list** records every payment with who approved it, newest first.

## Approving money (the one human-only action)

- Every pending request is a card showing:
  - the **amount**, large;
  - what it pays for, in words ("Pay rent on lease #1");
  - the agent's reason;
  - which agent prepared it (with its avatar);
  - **what checking will be after**.
  
  A request that would overdraw the account gets a red edge and says it will be refused, before you click.
- **Approve takes two clicks:** *Approve* → *Confirm: pay $2,400.00*. That's easy enough for routine use, but you can't pay by accident. *Reject* is one click, since it moves no money.
- **"Approving as"** in the top bar records your name on every payment. Approve and Reject stay disabled until a name is entered, with a hint explaining why. The name is remembered in this browser only.

## Creative details that make it enjoyable

- **Black and hot pink** (the class default style), with soft pink and violet glows in the background corners, so the dark screen feels warm rather than flat.
- **A live feeling while agents work:**
  - a pink "live" dot blinks on the feed;
  - three bouncing dots sit at the bottom of the feed, like someone typing;
  - a light sweeps across the working ticket's card;
  - new feed items rise in gently.
  
  The feed auto-scrolls only if you're already at the bottom, so it never yanks you away while you're reading.
- **Drafts look like paper.** Customer, landlord and vendor drafts are cream note cards with the writer's color on the edge and a dashed **NOT SENT** stamp. That's a visual promise that nothing leaves the building.
- **Toasts** in the corner confirm what just happened: the Boss picked up a ticket, a payment went through, a request was refused for insufficient cash.
- **Plain-English tool names:** "checked the invoice & vendor hold" rather than only `check_invoice_and_vendor_hold`. The real name stays beside it for anyone checking against the audit trail.
- **Respectful motion:** every animation turns off for users who set "reduce motion" in their system settings.

## Practical behavior

- The dashboard calls the backend at `http://localhost:8000` (`VITE_API_BASE` in `frontend/.env.development`). The backend allows the Vite origin `http://localhost:5173`.
- **Refresh rate:** every 1.5 seconds while agents are working and every 5 seconds otherwise. The feed asks only for entries newer than the last one it has, so refreshing stays light.
- **One run at a time.** While one ticket is being worked, the other tickets explain why they can't start yet: the tickets share the same cash.
- **Clear error states:** if the backend is down, a red banner says so and gives the exact command to start it. If an action fails (a 409 because agents are busy, or a refused payment), a toast explains why in plain words.
- **Reset shop** in the top bar restores the database to the original values for a fresh demo, after a confirm prompt.
