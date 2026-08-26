

This folder gives you power to interact with our test db.
Look at .env.example to see how the creds are stored in the actual .env.
Never read the actual .env - only use it programatically to interact with the DB.

This stuff is very very dangerous: YOU HAVE READWRITE USER, BUT YOU ARE ONLY ALLOWED TO DO READONLY OPERATIONS!!!!!
So be extremely careful about this.
And also, be careful to not run statements that would be extremely heavy and could have an impact on the db.