## SUGARDADDY
 A light-weight Glucose display for Ubuntu.

 Indicates high/low values and missed readings and is always just a glance away! Does __not__ make any sound!

Examples:

![Example](/media/example1.png) 

![Example of low](/media/example2.png)
# Requirements
 - Python 3.x
 - A [Nightscout Herokuapp](https://nightscout.github.io/vendors/heroku/new_user/)

# Usage
Enter your desired configurations into `setup.conf`:
- "YOUR-SITE" _must_ be on the form `xxxxx.herokuapp.com`, without "https://" or "www."
- If the "UNITS" option is anything _but_ `mmol/L`, then the units are displayed in mg/dl.
- "HIGH"/"LOW" are the thresholds (in your chosen units) for which the display should indicate high/low glucose levels.
- "OLD-THRESHOLD" is how old (in minutes) the latest reading must be before the display indicates that it hasn't got a new value in a while.

I recommend adding `SugarDaddy.py` as a [startup script](https://linuxconfig.org/how-to-run-script-on-startup-on-ubuntu-20-04-focal-fossa-server-desktop)
