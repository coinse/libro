var fs = require('fs');
require.extensions['.graphql'] = function (module, filename) {
    module.exports = fs.readFileSync(filename, 'utf8');
};
var queryPullRequestsData = require("./fetchLatestPullRequests");
var queryPullRequestData = require("./fetchPullRequest");

const { createApolloFetch } = require('apollo-fetch');

const apiURI = 'https://api.github.com/graphql';


async function fetchLatestPullRequests(name, owner) {
    return new Promise((resolve, reject) => {
        const fetch = createApolloFetch({
            uri: apiURI,
        });
        fetch.use(({ options }, next) => {
            if (!options.headers) {
                options.headers = {};  // Create the headers object if needed.
            }
            options.headers['Authorization'] = 'bearer ' + process.env.GH_OAUTH;
            next();
        });

        fetch({
            query: queryPullRequestsData,
            variables: {
                name: name,
                owner: owner
            },
        }).then(res => {
            console.log(res)
            if (!res.errors) {
                resolve(res.data)
            } else {
                console.log(owner + '/' + name + ' ' + res.errors[0].type)
                reject(res.errors)
            }
        }).catch(err => {
            console.log(err)
            reject(err)
        });
    });
}

async function fetchPullRequest(name, owner, number) {
    return new Promise((resolve, reject) => {
        const fetch = createApolloFetch({
            uri: apiURI,
        });
        fetch.use(({ options }, next) => {
            if (!options.headers) {
                options.headers = {};  // Create the headers object if needed.
            }
            options.headers['Authorization'] = 'bearer ' + process.env.GH_OAUTH;
            next();
        });

        fetch({
            query: queryPullRequestData,
            variables: {
                name: name,
                owner: owner,
                number: number
            },
        }).then(res => {
            console.log(res)
            if (!res.errors) {
                if (res.data.repository.pullRequest.closingIssuesReferences.edges.length > 0) {
                    resolve(res.data)
                } else {
                    reject(res.data)
                }
            } else {
                console.log(owner + '/' + name + ' ' + res.errors[0].type)
                reject(res.errors)
            }
        }).catch(err => {
            console.log(err)
            reject(err)
        });
    });
}

process.on('message', msg => {
    const dis = msg.split('/');
    const owner = dis[0];
    const name = dis[1];

    var PRNumbers = [];
    var pullRequests2022 = [];

    async function fetchPRs() {
        await fetchLatestPullRequests(name, owner).then(repoData => {
            const latestPRNumber = repoData.repository.pullRequests.edges[0].node.number;
            console.log(latestPRNumber)
            PRNumbers = [...Array(latestPRNumber).keys()].slice(latestPRNumber-2000, latestPRNumber);
        });

        console.log('Pull Requests Numbers to Collect: ', PRNumbers);

        var chunks = [];
        while (PRNumbers.length) chunks.push(PRNumbers.splice(0, 50));
        console.log(chunks);

        for (const PRNumbersChunk of chunks) {
           const promises = PRNumbersChunk.map(async (number) => await fetchPullRequest(name, owner, number).then(repoData => {
            console.log(repoData)
            pullRequests2022.push(repoData);
            }).catch(err => { console.log('Failed to patch PR: ', number); }));

            await Promise.all(promises)
            await new Promise(r => setTimeout(r, 5000)); // To avoid connection refused due to the consecutive requests
        }

        fs.writeFileSync(`data/${owner}_${name}.json`,
            JSON.stringify(pullRequests2022),
            'utf8', function (err) {
                if (err) {
                    process.send(false)
                }
                process.send(true)
            });
        process.send(true)
        process.exit(0);
    }

    fetchPRs()
});


