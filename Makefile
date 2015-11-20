test:
	runtests ZenPacks.zenoss.Layer2 -v;

testall:
	runtests ZenPacks.zenoss.Layer2 -v;
	cd simulation && make test;

PY_FILES=`find . -name '*.py' -not -path "*./build*" -not -path "./simulation/env/*" -not -path "*mock.py"`
pep8:
	pep8 --show-source --ignore=E402 --max-line-length=80 $(PY_FILES)

install-hook:
	cp pre-commit.sh .git/hooks/pre-commit
