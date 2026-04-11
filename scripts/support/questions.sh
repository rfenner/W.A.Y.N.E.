##
# ask_from_list
#
# $1 - the global to put the answer in
# $2 - the name of the list var to use
# $2 - the question to ask
##
function ask_from_list () {
  if [[ -z "$1" ]] || [[ -z "$2" ]] || [[ -z "$3" ]]; then
    echo "Need to pass 3 variables to ask_from_list."
    return 1
  fi
  local list_name="$2[@]"
  local list_values=("${!list_name}")
  idx=1
  for item in "${list_values[@]}"; do
    echo "${idx}) ${item}"
    ((idx++))
  done
  read -p "$3" selected
  if [[ $selected -lt 1 ]] || [[ $selected -ge $idx ]]; then
    echo "selected value is not a valid selection"
    return 1
  fi
  eval "$1=${list_values[$selected-1]}"
  return 0
}

##
# ask_question
#
# $1 - the global to put the answer in
# $2 - the question to ask
##
function ask_question() {
  if [[ -z "$1" ]] || [[ -z "$2" ]]; then
    echo "Need to pass 2 arguments to ask_question"
    return 1
  fi

  read -p "$2" answer

  eval "$1=\"$answer\""
  return 0
}

##
# ask_question_with_confirmation
#
# $1 - the global to put the answer in
# $2 - the question to ask
##
function ask_question_with_confirmation() {
  if [[ -z "$1" ]] || [[ -z "$2" ]]; then
    echo "Need to pass 2 arguments to ask_question_with_confirmation"
    return 1
  fi
  answer=""
  while [[ -z "${answer}" ]]; do
    read -p "${2}: " answer

    read -p "Do you wish to use '${answer}' (y/n)?" confirm
    confirm=$(echo "$confirm" | awk '{print tolower($0)}')

    if [[ "$confirm" != "y" ]] && [[ "$confirm" != "yes" ]]; then
      answer=""
    fi
  done

  eval "$1=\"$answer\""
  return 0
}

##
# ask_yes_no_question - ask a question that has a yes or no answer
#
# $1 - the global to put the answer into
# $2 - the question to ask
# $3 - whether to return an int = 0 or string = 1, defaults to int.
#      string will be 'yes' or 'no'
##
function ask_yes_no_question() {
    if [[ -z "$1" ]] || [[ -z "$2" ]]; then
    echo "Need to pass 2 arguments to ask_yes_no_question"
    return 1
  fi

  as_int=1
  if [[ -n "${3}" ]]; then
    as_int=$3
  fi

  read -p "${2}(y/n)" confirm

  confirm=$(echo "$confirm" | awk '{print tolower($0)}')

  if [[ "$confirm" != "y" ]] && [[ "$confirm" != "yes" ]]; then
    if [[ ${as_int} -eq 1 ]]; then
      answer=0
    else
      answer="\"no\""
    fi
  else
    if [[ ${as_int} -eq 1 ]]; then
      answer=1
    else
      answer="\"yes\""
    fi
  fi

  eval "$1=\"$answer\""
  return 0
}
