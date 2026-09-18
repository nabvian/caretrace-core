# Disclaimer

Please read this before you use CARETRACE for anything.

CARETRACE is an early research prototype. It is not a medical device, it has not
been clinically validated, and it is not cleared by any regulator (FDA, EU MDR,
UKCA, CDSCO, or any other). Do not use it to make, support, or influence a
decision about the care of a real person.

It does not diagnose, does not recommend treatment, and does not produce risk
scores. Anything it outputs — an extracted value, a detected conflict, a gap, a
timeline — can be wrong or incomplete and has to be checked by a qualified
person before anyone relies on it. I make no claim that it is accurate, complete,
or safe for any purpose.

The software is provided as is, with no warranty of any kind. The full terms are
in the [LICENSE](LICENSE). I accept no liability for how it is used.

On data: the demonstration case in this repository is fictional. Do not put real
patient data into any deployment that hasn't been independently reviewed for
security, privacy, and whatever law applies where you are (HIPAA, GDPR, the DPDP
Act, and so on). Running this software does not make a deployment compliant.

You're welcome to evaluate CARETRACE in a non-production, shadow-mode setting —
running it next to an existing, validated process rather than in place of it — to
help work out whether it's any good. That is not permission to use it in real
care.
