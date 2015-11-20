make test && make pep8
if [ "$?" -ne "0" ]; then
    echo -e "\e[31m Checks failed. Use --no-verify (-n) option to ignore checks and commit. \e[0m";
    exit 1;
else
    echo -e "\e[32m All checks OK! \e[0m"
fi
