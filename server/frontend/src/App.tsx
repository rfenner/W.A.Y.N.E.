import '@mantine/core/styles.css';
import './App.css'

import {Flex, MantineProvider, ScrollArea, Textarea} from "@mantine/core";
import {useCallback, useEffect, useState} from "react";
import {MagnifyingGlassIcon} from "@phosphor-icons/react";
import {ReadyState} from "react-use-websocket";
import useWebSocket from "react-use-websocket";

import DOMPurify from "dompurify";

function App() {
    const [messageHistory, setMessageHistory] = useState("");
    const [query, setQuery] = useState('');
    const {sendMessage, readyState} = useWebSocket('ws://localhost:18080/ws', {
        onMessage:(event) => {
            setMessageHistory(c=>c+DOMPurify.sanitize(event.data))
        }
    })

    const sendQuery = useCallback((query:string) => {
        sendMessage(query)
        setQuery('');
    }, [sendMessage])

    return (
        <>
            <MantineProvider>
                <div className="query-input">
                    <ScrollArea
                        h={400}
                        bd={'1px solid black'}
                        bdrs={5}
                        type={'auto'}
                        bg={'#f3f3f3'}
                        mt={10}
                    >
                        <div dangerouslySetInnerHTML={{ __html: messageHistory }} />

                    </ScrollArea>
                    <Flex justify={'center'}>
                    <Textarea
                        disabled={ReadyState.OPEN != readyState}
                        mt={10}
                        value={query}
                        w={'100%'}
                        h={300}
                        bdrs={5}
                        classNames={{
                            'input':'wayne-query-input'
                        }}
                        resize={'vertical'}
                        placeholder={ReadyState.OPEN == readyState ? 'What can I answer for you?':'Connecting to agent'}
                        onKeyDown={(e) => {
                            if (e.key == 'Enter' && e.ctrlKey) {
                                sendQuery(query);
                                e.preventDefault();
                                e.stopPropagation();
                                return
                            }
                        }
                        }
                        onChange={(e) => {setQuery(e.target.value)}}
                        rightSection={<MagnifyingGlassIcon
                            color={'black'}
                            onClick={() => {
                                sendQuery(query);
                            }}
                        />}
                    />
                    </Flex>
                </div>
            </MantineProvider>
        </>
    )
}

export default App
