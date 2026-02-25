import httpx, time
base='http://127.0.0.1:8000'
client=httpx.Client()
print('health', client.get(base+'/health').json())
print('llm', client.get(base+'/llm/health', params={'do_ping':'false'}).json())
print('start', client.post(base+'/adapters/start').json())
print('stop', client.post(base+'/adapters/stop').json())
print('list', client.get(base+'/rules/list').json())
sample={'rule_id':'test-rule','name':'t','description':'d','target_session':{'mode':'exact','query':'chat-1'},'topic_hints':['a'],'score_threshold':0.5,'enabled':True,'parameters':[]}
print('upsert', client.post(base+'/rules', json=sample).json())
print('after', client.get(base+'/rules/list').json())
print('delete', client.post(base+f"/rules/delete/{sample['rule_id']}").json())
print('final', client.get(base+'/rules/list').json())
print('gen', client.post(base+'/rule-generation', json={'utterance':'测试','use_external':False}).json())
