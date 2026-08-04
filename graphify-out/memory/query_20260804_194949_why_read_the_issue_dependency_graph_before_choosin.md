---
type: "query"
date: "2026-08-04T19:49:49.731233+00:00"
question: "Why read the issue dependency graph before choosing the next ticket?"
contributor: "graphify"
outcome: "useful"
---

# Q: Why read the issue dependency graph before choosing the next ticket?

## Answer

Read the dependency graph before choosing the next ticket -- the obvious
capstone is often blocked, and the useful pick is the one that unblocks it.

Closing out #154 I went to propose the next task and reached for #150
("/clear-prep calls the tasks instead of describing them"), because it is the
visible payoff of the whole #143 programme and because I had just spent a
session performing by hand the very steps it automates.

#150 is blocked by #147, #148 and #149. Only #147 was done. Reading each
candidate's "Blocked by" section gave the real picture:

    #145 done --+--> #148  READY   (leaf blocker of #150)
                |
    #144 READY -+--> #149  blocked --+
                                     +--> #150  CAPSTONE
    #147 done ---------------------- +

    ready set: #144, #148, #151, #158
    #149 and #150 cannot be started at all

That reframes the choice completely. #144 is the ONLY blocker of #149, so it is
the pick that turns the longest chain live; #148 is a leaf that unblocks nothing
but #150. Without the graph I would have proposed a ticket that could not be
started, or picked the leaf and left the chain dead.

WHAT TO DO: before proposing or accepting a next task, read the Blocked by
section of every candidate AND of the ticket you actually want to reach, and
state the graph. It takes one gh call per issue. The signal it gives -- which
ready ticket unblocks the most -- is not visible from titles, labels, or
recency, and "ready-for-agent" on every candidate says nothing about order.

## Outcome

- Signal: useful