
May 17
The IGM optimization is not working,
this is probably because we only have 5 structures,
and we are trying to optimize the HiC data.

Next time, we can silence the HiC data,
and run IGM only with the Speckle data.

June 2
We have a path issue: it doesn't find the speckles.pkl file.
We tried looking at how this problem was solved for .hcs data,
but for now we haven't been able to solve it.

June 14
We used the absolute path to temporarily solve the problem,
but the violation score didn't improve throughout the iterations.
We repeated the IGM run by removing the Speckle restraint, and
the violation score improved. This means that the Speckle restraint
is not working properly.
