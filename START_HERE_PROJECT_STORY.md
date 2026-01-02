# Start Here: The Project Story

This document explains the entire project from start to finish. No technical background is required. If you only read one file, read this one.

---

## The Real-World Problem

Imagine you run marketing for an online retailer. You have a list of 100,000 customers. You want to send a promotional email, but you can only afford to send 10,000 emails this month.

The question is simple: **Which 10,000 customers should you email?**

This is not a hypothetical problem. Every marketing team with a limited budget faces this decision. The answer determines how much revenue the campaign generates—and how much money is wasted.

---

## How Companies Usually Solve This

The conventional approach is to predict who is most likely to buy.

You build a model that scores each customer based on their chance of making a purchase. Then you email the top 10,000—the people with the highest scores.

This sounds logical. Why email someone who probably won't buy? For most teams, this is a reasonable default—it uses available data, it's easy to explain, and it's better than guessing.

---

## Why That Can Go Wrong

Here's the problem: some of your best customers were going to buy anyway.

Suppose a customer visits your website every week and has purchased five times in the last month. Your model gives them a high score. You send them an email. They buy.

But here's the question: did the email cause the purchase? Or would they have bought regardless?

If they would have bought anyway, the email was wasted. You used one of your 10,000 slots on someone who didn't need convincing.

Meanwhile, there might be a customer who almost never buys—but would have responded to the email. You didn't email them because their score was too low. That's a missed opportunity.

The conventional approach optimises for conversion. But what you actually want is *incremental* conversion—sales that happen *because* of the email, not sales that happen *regardless* of it.

---

## What Incremental Impact Means

Incremental impact is the difference between two outcomes:

1. What happens if you send the email.
2. What happens if you don't.

Some customers will buy either way. For them, the email adds nothing. The incremental impact is zero.

Some customers will never buy, no matter what. For them too, the email adds nothing.

The valuable customers are in the middle: people who won't buy on their own, but will buy if you nudge them. These are the persuadable customers. The email makes a difference for them.

The goal is to find these customers and prioritise them.

---

## What This Project Did Differently

This project uses data from real marketing experiments.

In these experiments, some customers received a marketing message. Others were deliberately held out as a control group—they received nothing. Everyone's behaviour was recorded.

This experimental design allows us to estimate what would have happened under both conditions. For customers who received the message, we observe their actual behaviour. For customers in the control group, we observe what happens without the message.

By comparing treated and control groups, we can estimate the incremental effect of the message.

The project then simulates different targeting strategies: What if we had emailed the top 10%? The top 20%? The top 50%? How many extra sales would each strategy have produced?

This kind of analysis is harder than standard prediction. It requires experimental data (which many companies don't have), it's more fragile (small samples produce noisy estimates), and it's harder to explain to stakeholders. But when it works, it directly answers the business question: *who should we contact?*

---

## What Was Tested

The project compared three targeting strategies:

### Strategy 1: Random Selection

Pick 10% of customers at random. This is the baseline. It tells us what happens when we don't try to be smart.

### Strategy 2: Propensity-Based Selection

Pick the 10% of customers most likely to convert. This is the conventional approach. It sounds good, but as discussed above, it can waste budget on customers who would have converted anyway.

### Strategy 3: Uplift-Based Selection

Pick the 10% of customers with the highest estimated incremental effect. These are the customers where the email is predicted to make the biggest difference.

The project ran these strategies on past data and measured how many extra conversions each one produced.

---

## What Actually Happened

The results were mixed—and that's the point.

In the Women's Email experiment, uplift-based targeting clearly outperformed the alternatives. Customer responses varied widely: some were persuadable, others were not. The uplift model found the difference and exploited it.

In the Men's Email experiment, the advantage was smaller and less consistent. There was less variation in how customers responded to treatment, so the uplift model had less to work with.

In the Criteo advertising dataset, all strategies produced similar results. Effects were tiny across the board. When the incremental impact of advertising is marginal, no targeting method can extract much value.

The project also computed confidence intervals to measure uncertainty. In many cases, the observed differences were within the range of random variation. This means we cannot confidently say one strategy is better than another—the data simply isn't strong enough.

---

## Why This Matters for Real Businesses

This project demonstrates a different way of thinking about marketing decisions.

Instead of asking *"Who will convert?"*, it asks *"Who will convert because of our action?"*

This shift has practical consequences:

- **Cost control**: If high-likelihood customers convert anyway, you can save money by not targeting them.
- **Experimentation**: The only way to measure incremental impact is through controlled experiments. This project shows how to use experimental data for decision-making.
- **Honesty about uncertainty**: Not every difference is real. Confidence intervals force discipline. They prevent teams from over-interpreting noise.

---

## What This Project Does NOT Claim

This project does not claim that uplift modelling is always better.

In some datasets, it helped. In others, it did not. The value of uplift modelling depends on whether persuadable customers exist and whether they can be identified from available data.

This project does not claim that the methods used are optimal. The models are simple by design. The focus is on the evaluation framework, not on model sophistication.

This project does not claim universal applicability. The datasets used are specific to email and advertising. Results may differ in other domains.

The honest conclusion is: uplift-based targeting can work, but it is not a guaranteed improvement. It should be tested empirically, with proper uncertainty quantification, before being deployed.
