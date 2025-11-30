# MODULE-USP_VIREL
---- MODULE USP_VIREL ----
EXTENDS Integers, FiniteSets, TLC

CONSTANTS 
    Domains, 
    EpochMax, 
    LamportMax

VARIABLES 
    state, 
    epoch, 
    lamport, 
    quorum_votes, 
    provisional_timer

Init ==
    /\ state \in {"OPERATIONAL", "SAFE_ON"}
    /\ epoch = 0
    /\ lamport = 0
    /\ quorum_votes \in [d \in Domains |-> Seq({"HALT", "RES"})]
    /\ provisional_timer = 0