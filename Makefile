test:
	runtests ZenPacks.zenoss.Layer2 -v;

testall:
	runtests ZenPacks.zenoss.Layer2 -v;
	cd simulation && make test;

pep8:
	./check_pep8.sh

install-hook:
	cp pre-commit.sh .git/hooks/pre-commit
