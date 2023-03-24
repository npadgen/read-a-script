install: requirements.txt
	pipx install --include-deps .
	pipx inject $$(basename $(PWD)) $$(sed 's/;.*//' requirements.txt)

uninstall:
	pipx uninstall .

reinstall:	uninstall install

force:
	pipx install --force --include-deps .
	pipx inject $$(basename $(PWD)) $$(sed 's/;.*//' requirements.txt)

requirements.txt: poetry.lock
	poetry export -f requirements.txt -o requirements.txt --without-hashes
